# This class is used to define different instructions for different languages
class Instructions:
    _language: str

    def __init__(self, lang: str):
        self._language = lang

    def get_queryInstruction(self, n_queries: int, user_question: str) -> str:
        if self._language.upper() == "EN":
            return self._instQueries_EN(n_queries, user_question)
        elif self._language.upper() == "PTBR":
            return self._instQueries_PTBR(n_queries, user_question)
        else:
            return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_promptInstruction(self, context: str, user_question: str) -> str:
        if self._language.upper() == "EN":
            return self._instPrompt_EN(context, user_question)
        elif self._language.upper() == "PTBR":
            return self._instPrompt_PTBR(context, user_question)
        else:
            return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_errSources(self) -> str:
        if self._language.upper() == "EN":
            return self._errSources_EN()
        elif self._language.upper() == "PTBR":
            return self._errSources_PTBR()
        else:
            return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_queryResponseFormat(self) -> dict:
        """JSON schema for the query generation step."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "query_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "thought_process": {"type": "string"}
                    },
                    "required": ["queries", "thought_process"],
                    "additionalProperties": False
                }
            }
        }

    def get_promptResponseFormat(self) -> dict:
        """JSON schema for the answer generation step."""
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "answer_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer": {"type": "string"},
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "thought_process": {"type": "string"}
                    },
                    "required": ["answer", "sources", "thought_process"],
                    "additionalProperties": False
                }
            }
        }

    # ── English ───────────────────────────────────────────────────────────────

    def _instQueries_EN(self, n_queries: int, user_question: str) -> str:
        return (
            f"### TASK\n"
            f"Generate exactly {n_queries} short search queries to find information "
            f"that answers the question below.\n\n"
            f"### OUTPUT FORMAT\n"
            f"Respond ONLY with a JSON object in this exact format:\n"
            f"{{\n"
            f'  "queries": ["query 1", "query 2", "query 3"],\n'
            f'  "thought_process": "brief explanation of why you chose these queries"\n'
            f"}}\n\n"
            f"### QUERY RULES\n"
            f"- Each query must be 5-10 words.\n"
            f"- Queries must be in the same language as the question.\n"
            f"- Queries must be meaningfully different from each other.\n\n"
            f"### EXAMPLE\n"
            f"Question: What are the tax brackets for 2024?\n"
            f"{{\n"
            f'  "queries": ["tax brackets 2024", "income tax rates federal", "IRS tax table current year"],\n'
            f'  "thought_process": "Searched for the brackets directly, then by rate type, then by the issuing authority."\n'
            f"}}\n\n"
            f"### YOUR TURN\n"
            f"Question: {user_question}\n"
            f"{{"
        )

    def _instPrompt_EN(self, context: str, user_question: str) -> str:
        return (
            f"### ROLE\n"
            f"You are a document assistant. Answer questions exclusively from the provided sources.\n\n"
            f"### OUTPUT FORMAT\n"
            f"Respond ONLY with a JSON object in this exact format:\n"
            f"{{\n"
            f'  "answer": "your final answer here",\n'
            f'  "sources": ["Source name p.X", "Source name p.Y"],\n'
            f'  "thought_process": "your internal reasoning about which sources were relevant"\n'
            f"}}\n\n"
            f"### ANSWER RULES\n"
            f"- The 'answer' field must use ONLY information from the sources below.\n"
            f"- The 'answer' field must be clean and direct — no reasoning, no hedging.\n"
            f"- The 'sources' field must list every source used.\n"
            f"- If the answer is not found in any source, set 'answer' to exactly: '{self._errSources_EN()}' and 'sources' to [].\n"
            f"- The 'thought_process' field is for your internal reasoning only — it will not be shown to the user.\n\n"
            f"### SOURCES\n"
            f"{context}\n\n"
            f"### QUESTION\n"
            f"{user_question}\n\n"
            f"{{"
        )

    def _errSources_EN(self) -> str:
        return "Information not found within provided data."

    # ── Portuguese ────────────────────────────────────────────────────────────

    def _instQueries_PTBR(self, n_queries: int, user_question: str) -> str:
        return (
            f"### TAREFA\n"
            f"Gere exatamente {n_queries} consultas de pesquisa curtas para encontrar "
            f"informações que respondam a pergunta abaixo.\n\n"
            f"### FORMATO DE SAÍDA\n"
            f"Responda APENAS com um objeto JSON neste formato exato:\n"
            f"{{\n"
            f'  "queries": ["consulta 1", "consulta 2", "consulta 3"],\n'
            f'  "thought_process": "breve explicação de por que você escolheu essas consultas"\n'
            f"}}\n\n"
            f"### REGRAS DAS CONSULTAS\n"
            f"- Cada consulta deve ter 5-10 palavras.\n"
            f"- As consultas devem estar no mesmo idioma que a pergunta.\n"
            f"- As consultas devem ser significativamente diferentes entre si.\n\n"
            f"### EXEMPLO\n"
            f"Pergunta: O que são os impostos no Brasil em 2024?\n"
            f"{{\n"
            f'  "queries": ["impostos Brasil 2024", "alíquotas imposto de renda", "tabela fiscal ano atual"],\n'
            f'  "thought_process": "Busquei diretamente pelos impostos, depois pelas alíquotas e por fim pela tabela oficial."\n'
            f"}}\n\n"
            f"### SUA VEZ\n"
            f"Pergunta: {user_question}\n"
            f"{{"
        )

    def _instPrompt_PTBR(self, context: str, user_question: str) -> str:
        return (
            f"### FUNÇÃO\n"
            f"Você é um assistente de documentos. Responda perguntas exclusivamente com base nas fontes fornecidas.\n\n"
            f"### FORMATO DE SAÍDA\n"
            f"Responda APENAS com um objeto JSON neste formato exato:\n"
            f"{{\n"
            f'  "answer": "sua resposta final aqui",\n'
            f'  "sources": ["Nome da fonte p.X", "Nome da fonte p.Y"],\n'
            f'  "thought_process": "seu raciocínio interno sobre quais fontes eram relevantes"\n'
            f"}}\n\n"
            f"### REGRAS DA RESPOSTA\n"
            f"- O campo 'answer' deve usar APENAS informações das fontes abaixo.\n"
            f"- O campo 'answer' deve ser limpo e direto — sem raciocínio, sem hesitações.\n"
            f"- O campo 'sources' deve listar todas as fontes utilizadas.\n"
            f"- Se a resposta não for encontrada em nenhuma fonte, defina 'answer' como exatamente: '{self._errSources_PTBR()}' e 'sources' como [].\n"
            f"- O campo 'thought_process' é apenas para seu raciocínio interno — não será exibido ao usuário.\n\n"
            f"### FONTES\n"
            f"{context}\n\n"
            f"### PERGUNTA\n"
            f"{user_question}\n\n"
            f"{{"
        )

    def _errSources_PTBR(self) -> str:
        return "Nenhuma informação encontrada."