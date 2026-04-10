from openai import OpenAI
from src.memory import get_collection, store, recall, pdf_ingest
from src.instructions.instructions import Instructions
from pathlib import Path
import chromadb
import json

class Model:
    _language       : str
    _sources        : list[str]
    _instructions   : Instructions
    _collection     : chromadb.Collection
    _client         : OpenAI

    _query_count    : int

    def __init__(self, query_count : int, lang : str):
        self._query_count = query_count
        self._language = lang
        self._instructions = Instructions(lang=lang)
        self._collection = get_collection()
        self._client = OpenAI(base_url=f"http://127.0.0.1:1234/v1", api_key="")

        self._loadPdfs()
        pass

    def _loadPdfs(self):
        data_path = Path(__file__).resolve().parent.parent / "data"
        pdf_files = sorted(data_path.glob("*.pdf"))
        # print(f"files: {[f.name for f in pdf_files]}")
        for pdf_file in pdf_files:
            # print(f"Adding file: {pdf_file.name}")
            pdf_ingest(self._collection, str(pdf_file), pdf_file.name)


    def _queryMemories(self,user_question : str) -> list[str]:
        instruction = self._instructions.get_queryInstruction(n_queries=self._query_count, user_question=user_question)
        completion = self._client.chat.completions.create(
            model="deepseek-r1-distill-qwen-1.5b",
            messages=[
                {"role": "user", "content": instruction}
            ],
            temperature=0.1,
            response_format=self._instructions.get_responseFormat()
        )
        queries = json.loads(completion.choices[0].message.content)['queries']
        return [q for q in queries if isinstance(q, str)]
    
    def _queryRecall(self, queries : list[str], n_results : int = 5) -> list[dict]:
        seen_ids = set()
        all_results = []
        
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
        return all_results[:n_results]
    
    def _getQueries(self, user_question : str, score_treshold : float = 0.45) -> str:
        queries = self._queryMemories(user_question=user_question)
        queryRecall = self._queryRecall(queries=queries, n_results=5)

        if not queryRecall or queryRecall[0]["score"] < score_treshold:
            return "Information not found within provided data."
        
        return "\n\n".join(
                f"[Source {i+1} | {r['metadata']['source']} p.{r['metadata'].get('page','?')}]\n{r['text']}"
                for i, r in enumerate(queryRecall))

    def prompt(self, user_question : str) -> str:
        memoryData = self._getQueries(user_question=user_question)
        prompt = self._instructions.get_promptInstruction(context=memoryData, user_question=user_question)

        print(f"prompt: {prompt}")

        completion = self._client.chat.completions.create(
            model="meta-llama-3.1-8b-instruct",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        return completion.choices[0].message.content

    
