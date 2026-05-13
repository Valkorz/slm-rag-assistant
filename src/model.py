from openai import OpenAI
from src.memory import get_collection, store, recall, pdf_ingest
from src.instructions.instructions import Instructions
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

    # Common Spanish/English words that shouldn't appear in PT queries and vice versa
    _SPANISH_MARKERS = {"impuesto", "año", "también", "según", "más", "están", "será", "para"}
    _ENGLISH_MARKERS = {"the", "and", "for", "with", "income", "federal", "tax", "rate"}
    _PT_MARKERS      = {"imposto", "renda", "alíquota", "declaração", "contribuinte", "tabela"}

    def __init__(self, query_count : int, lang : str = "EN", query_model : str = "deepseek-r1-distill-qwen-1.5b", reason_model : str = "meta-llama-3.1-8b-instruct"):
        self._query_count = query_count
        self._language = lang
        self._files = []
        self._instructions = Instructions(lang=lang)
        self._collection = get_collection()
        self._query_model = query_model
        self._reasoning_model = reason_model
        # self._client = OpenAI(base_url=f"http://127.0.0.1:1234/v1", api_key="")
        self.model_manager = ModelManager()

        self._loadPdfs()

        print(f"Initialized model with language: {self._language}")
        pass

    def set_language(self, lang : str):
        self._language = lang
        self._instructions.set_language(lang=lang)

    def set_query_model(self, name : str):
        self._query_model = name

    def set_resoning_model(self, name : str):
        self._reasoning_model = name

    def _loadPdfs(self):
        data_path = Path(__file__).resolve().parent.parent / "data"
        pdf_files = sorted(data_path.glob("*.pdf"))
        for pdf_file in pdf_files:
            pdf_ingest(self._collection, str(pdf_file), pdf_file.name)
            self._files.append(pdf_file.name)

    def addPdfs(self, pdf_files : list[dict]):
        print(f"Adding pdfs: {pdf_files}")
        for pdf_file in pdf_files:
            pdf_ingest(self._collection, str(pdf_file['path']), pdf_file['name'])
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

        raise TypeError("Model completion format is not supported")

    def _parse_completion_json(self, completion) -> dict:
        if isinstance(completion, dict) and "queries" in completion:
            return completion

        text = self._extract_completion_text(completion)
        return self._extract_json_from_text(text)

    def _extract_json_from_text(self, text: str) -> dict:
        candidates = []

        # Strategy 1: fenced code blocks
        for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
            candidates.append(m.group(1).strip())

        # Strategy 2: balanced brace extraction
        if not candidates:
            starts = [m.start() for m in re.finditer(r"\{", text)]
            for i in starts:
                depth = 0
                for j in range(i, len(text)):
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                        if depth == 0:
                            candidates.append(text[i:j+1])
                            break

        # Strategy 3: model omitted the opening brace due to prompt priming
        if not candidates:
            stripped = text.strip()
            if stripped and not stripped.startswith("{"):
                candidates.append("{" + stripped)

        # Strategy 4: direct parse of raw text as last resort
        candidates.append(text)

        last_valid = None
        for cand in candidates:
            try:
                parsed = json.loads(cand)
                if isinstance(parsed, dict):
                    last_valid = parsed
            except Exception:
                continue

        if last_valid is not None:
            return last_valid

        raise ValueError(f"No valid JSON object found in model output.\nRaw text: {text[:200]}")

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
        self.model_manager.load(model_name=self._query_model)
        raw = self.model_manager.create_completion(prompt=instruction)['choices'][0]['text']

        try:
            parsed = self._extract_json_from_text(raw)
        except ValueError:
            return []

        queries = parsed.get('queries', [])

        valid_queries = [q for q in queries if isinstance(q, str) and self._is_query_valid_language(query=q,expected_lang=self._language)]
        if len(valid_queries) < max(1, self._query_count // 2):
            print(f"Not enough valid search queries. Fallback enabled.")
            valid_queries = self._fallback_queries(user_question=user_question)

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
    
    def _queryRecall(self, queries : list[str], n_results : int = 5) -> list[dict]:
        seen_ids = set()
        all_results = []
        SCORE_MINIMUM = 0.6
        
        for query in queries:
            results = self._collection.query(query_texts=[query], n_results=3)
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
        return [r for r in all_results if r["score"] >= SCORE_MINIMUM]
    
    def _getQueries(self, user_question : str, score_treshold : float = 0.45) -> str:
        queries = self._queryMemories(user_question=user_question)
        queryRecall = self._queryRecall(queries=queries, n_results=5)
        print(f"Query recall: {queryRecall}, queries: {queries}")

        if not queryRecall or queryRecall[0]["score"] < score_treshold:
            return self._instructions.get_errSources()
        
        return "\n\n".join(
                f"[Source {i+1} | {r['metadata']['source']} p.{r['metadata'].get('page','?')}]\n{r['text']}"
                for i, r in enumerate(queryRecall))

    def prompt(self, user_question: str) -> str:
        memoryData = self._getQueries(user_question=user_question)
        prompt_text = self._instructions.get_promptInstruction(
            context=memoryData,
            user_question=user_question
        )
        self.model_manager.load(model_name=self._reasoning_model)
        raw = self.model_manager.create_completion(prompt=prompt_text)
        raw_text = raw.get('choices', [{}])[0].get('text', '')
        print(f"prompt response: {raw_text}")

        try:
            parsed = self._extract_json_from_text(raw_text)
        except ValueError:
            return raw_text

        try:
            return self._extract_completion_text(parsed)
        except TypeError:
            return json.dumps(parsed)

    
