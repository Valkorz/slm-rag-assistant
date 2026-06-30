from openai import OpenAI
from src.memory import get_collection, store, recall, pdf_ingest
from src.instructions.instructions import Instructions
from src.utils.logger import logger
from pathlib import Path
from .model_manager import ModelManager
import chromadb
import json
import re

class Model:
    #public
    model_manager       : ModelManager

    #private
    _language           : str
    _files              : list[str]
    _instructions       : Instructions
    _collection         : chromadb.Collection
    _client             : OpenAI
    
    _query_count        : int
    
    #Model settings
    _query_model        : str
    _reasoning_model    : str
    _temperature        : float
    _query_temperature  : float
    _score_minimum      : float
    _chunk_min_density   : float
    _chunk_min_diversity : float
    _chunk_min_avg_sentence : float

    # Common Spanish/English words that shouldn't appear in PT queries and vice versa
    _SPANISH_MARKERS = {"impuesto", "año", "también", "según", "más", "están", "será", "para"}
    _ENGLISH_MARKERS = {"the", "and", "for", "with", "income", "federal", "tax", "rate"}
    _PT_MARKERS      = {"imposto", "renda", "alíquota", "declaração", "contribuinte", "tabela"}

    def __init__(self, query_count : int, lang : str = "EN", query_model : str = "deepseek-r1-distill-qwen-1.5b", reason_model : str = "meta-llama-3.1-8b-instruct", mode: str = "document", temperature: float = 0.1, query_temperature: float = 0.1, score_minimum: float = 0.6, chunk_min_density: float = 0.55, chunk_min_diversity: float = 0.40, chunk_min_avg_sentence: float = 5.0):
        self._query_count = query_count
        self._language = lang
        self._files = []
        self._instructions = Instructions(lang=lang, mode=mode)
        self._collection = get_collection(lang=lang)
        self._query_model = query_model
        self._reasoning_model = reason_model
        self._temperature = temperature
        self._query_temperature = query_temperature
        self._score_minimum = score_minimum
        self._chunk_min_density = chunk_min_density
        self._chunk_min_diversity = chunk_min_diversity
        self._chunk_min_avg_sentence = chunk_min_avg_sentence
        # self._client = OpenAI(base_url=f"http://127.0.0.1:1234/v1", api_key="")
        self.model_manager = ModelManager()

        self._loadPdfs()

        logger.info(f"Initialized model with language: {self._language}")
        pass

    def set_language(self, lang: str):
        self._language = lang
        self._instructions.set_language(lang=lang)
        self._collection = get_collection(lang=lang)
        self._loadPdfs()

    def set_query_model(self, name : str):
        self._query_model = name

    def set_resoning_model(self, name : str):
        self._reasoning_model = name

    def set_mode(self, mode: str):
        self._instructions.set_mode(mode)

    def set_temperature(self, temperature: float):
        self._temperature = temperature

    def set_query_count(self, query_count: int):
        self._query_count = query_count

    def set_query_temperature(self, temperature: float):
        self._query_temperature = temperature

    def set_score_minimum(self, score_minimum: float):
        self._score_minimum = score_minimum

    def set_chunk_validation(self, min_density: float, min_diversity: float, min_avg_sentence: float):
        self._chunk_min_density = min_density
        self._chunk_min_diversity = min_diversity
        self._chunk_min_avg_sentence = min_avg_sentence

    def _loadPdfs(self):
        data_path = Path(__file__).resolve().parent.parent / "data"
        pdf_files = sorted(data_path.glob("*.pdf"))
        for pdf_file in pdf_files:
            pdf_ingest(self._collection, str(pdf_file), pdf_file.name,
                       min_density=self._chunk_min_density,
                       min_diversity=self._chunk_min_diversity,
                       min_avg_sentence=self._chunk_min_avg_sentence)
            self._files.append(pdf_file.name)

    def addPdfs(self, pdf_files : list[dict]):
        logger.info(f"Adding pdfs: {pdf_files}")
        for pdf_file in pdf_files:
            extra_metadata = None
            metadata_value = pdf_file.get('metadata')
            if isinstance(metadata_value, str) and metadata_value.strip():
                extra_metadata = {"tag": metadata_value.strip()}

            pdf_ingest(
                self._collection,
                str(pdf_file['path']),
                pdf_file['name'],
                extra_metadata=extra_metadata,
                min_density=self._chunk_min_density,
                min_diversity=self._chunk_min_diversity,
                min_avg_sentence=self._chunk_min_avg_sentence,
            )
            self._files.append(pdf_file['name'])

    def _extract_completion_text(self, completion) -> str:
        if isinstance(completion, str):
            return completion

        if isinstance(completion, dict):
            choices = completion.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    text = first.get("text")
                    if isinstance(text, str):
                        return text

                    message = first.get("message")
                    if isinstance(message, dict):
                        content = message.get("content")
                        if isinstance(content, str):
                            return content

        error_message = "Model completion format is not supported"
        logger.error(error_message)
        raise TypeError(error_message)

    def _parse_completion_json(self, completion) -> dict:
        if isinstance(completion, dict) and "queries" in completion:
            return completion

        text = self._extract_completion_text(completion)
        return self._extract_json_from_text(text)

    @staticmethod
    def _balanced_objects(text: str) -> list[str]:
        """Return every top-level {...} substring, in the order they appear."""
        objects = []
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
                if depth == 0:
                    objects.append(text[start:i + 1])
        logger.info(f"Balanced objects: {text}")
        return objects

    def _extract_json_from_text(self, text: str, expected_keys: tuple = ()) -> dict:
        stripped = text.strip()

        primed = stripped if stripped.startswith("{") else "{" + stripped

        candidates = [primed]
        candidates.extend(self._balanced_objects(primed))
        for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
            candidates.append(m.group(1).strip())
        candidates.append(stripped)

        fallback = None
        for cand in candidates:
            try:
                parsed = json.loads(cand)
            except Exception:
                continue
            if not isinstance(parsed, dict):
                continue
            # Prefer the FIRST object that has the fields we asked for; this skips
            # stray/echoed template objects that appear later in the output.
            if expected_keys and not any(k in parsed for k in expected_keys):
                fallback = fallback if fallback is not None else parsed
                continue

            logger.info(f"Parsed JSON: {parsed}")
            return parsed

        if fallback is not None:
            return fallback
        
        error_message = f"No valid JSON object found in model output.\nRaw text: {text[:200]}"
        logger.error(error_message)
        raise ValueError(error_message)

    def _is_query_valid_language(self, query: str, expected_lang: str) -> bool:
        words = set(query.lower().split())
    
        if expected_lang == "PTBR":
            # Reject if it has Spanish markers but no Portuguese markers
            has_spanish = bool(words & self._SPANISH_MARKERS)
            has_pt      = bool(words & self._PT_MARKERS)
            if has_spanish and not has_pt:
                return False

        elif expected_lang == "EN":
            # Reject if it has no English markers at all
            has_english = bool(words & self._ENGLISH_MARKERS)
            has_spanish = bool(words & self._SPANISH_MARKERS)
            if has_spanish and not has_english:
                return False

        return True
    
    def _queryMemories(self, user_question: str) -> list[str]:
        instruction = self._instructions.get_queryInstruction(
            n_queries=self._query_count,
            user_question=user_question
        )

        logger.info(f"Query generation instructions \n{instruction}")
        self.model_manager.load(model_name=self._query_model)
        raw = self.model_manager.create_completion(prompt=instruction, temperature=self._query_temperature, stop=["###", "```"])['choices'][0]['text']
        logger.info(f"Raw queries: {raw}")

        try:
            parsed = self._extract_json_from_text(raw, expected_keys=("queries",))
        except ValueError:
            return []

        queries = parsed.get('queries', [])

        valid_queries = [q for q in queries if isinstance(q, str) and self._is_query_valid_language(query=q,expected_lang=self._language)]
        if len(valid_queries) < max(1, self._query_count // 2):
            logger.warn(f"Not enough valid search queries. Fallback enabled.")
            valid_queries = self._fallback_queries(user_question=user_question)

        logger.info(f"Valid queries: {valid_queries}")
        return valid_queries
            
    # If no valid queries are generated by the model, create a list of keywords from the question itself
    # OR simply return the question.
    def _fallback_queries(self, user_question: str) -> list[str]:
        stopwords = {"o", "a", "os", "as", "de", "do", "da", "em", "para", "que",
                     "the", "a", "an", "is", "are", "for", "of", "in", "what"}
        words = [w for w in re.findall(r'\b\w{4,}\b', user_question.lower()) 
                 if w not in stopwords]

        if not words:
            return [user_question]

        queries = []
        for i in range(min(3, len(words))):
            chunk = words[i:i+3]
            queries.append(" ".join(chunk))

        return queries or [user_question]       
    
    def _queryRecall(self, queries : list[str], n_results : int = 5, doc_type: str = None) -> list[dict]:
        seen_ids = set()
        all_results = []

        where = { "type": doc_type } if doc_type else None
        
        for query in queries:
            results = self._collection.query(query_texts=[query], n_results=3, where=where)
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            ):
                chunk_id = f"{meta['source']}::{meta['page']}::{meta['chunk_index']}"
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    all_results.append(
                        {
                            "text":doc,
                            "metadata": meta,
                            "score": round(1 - dist, 3)
                        }
                    )
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return [r for r in all_results if r["score"] >= self._score_minimum]
    
    # Base context assembler
    def _build_context(self, queries: list[str]) -> str:
        results = self._queryRecall(queries=queries)       
        if not results:
            logger.error("No sources could be recalled.")
            return self._instructions.get_errSources()
        
        logger.info(f"Query recall results: {results}")

        return "\n\n".join(
            f"[Source {i+1} | {r['metadata']['source']} p.{r['metadata'].get('page','?')}]\n{r['text']}"
            for i, r in enumerate(results)
        )
    
    def _getQueries(self, user_question : str) -> str:
        queries = self._queryMemories(user_question=user_question)
        return self._build_context(queries=queries)

    def prompt(self, user_question: str) -> str:
        context = self._getQueries(user_question=user_question)
        logger.info(f"Generation temperatures: \nQuery temperature: {self._query_temperature}\nResponse temperature:{self._temperature}")
        logger.info(f"Provided context: {context}")

        prompt_text = self._instructions.get_promptInstruction(
            context=context,
            user_question=user_question
        )

        logger.info(f"Prompt instruction: \n{prompt_text}")

        self.model_manager.load(model_name=self._reasoning_model)
        raw = self.model_manager.create_completion(prompt=prompt_text, temperature=self._temperature, stop=["###", "```"])
        raw_text = raw.get('choices', [{}])[0].get('text', '')
        logger.debug(f"Response: \n{raw_text}")

        try:
            parsed = self._extract_json_from_text(raw_text, expected_keys=("answer",))
        except ValueError:
            logger.error("Failed to extract JSON from text.")
            return raw_text
    
        try:
            return self._extract_completion_text(parsed)
        except TypeError:
            logger.error("Failed to extract completion text.")
            return json.dumps(parsed)

    
