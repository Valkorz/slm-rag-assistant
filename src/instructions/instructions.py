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

    def get_responseFormat(self) -> dict[str, object]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "reasoning_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "queries": {"type": "array"},
                    },
                    "required": ["queries"],
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
            f"### STRICT OUTPUT RULES\n"
            f"- Output ONLY a raw JSON array of strings.\n"
            f"- No text before or after the array.\n"
            f"- No explanations, no reasoning, no thought process.\n"
            f"- Each query must be 5-10 words.\n\n"
            f"### EXAMPLES\n"
            f"Question: What are the tax brackets for 2024?\n"
            f'Output: ["tax brackets 2024", "income tax rates federal", "IRS tax table current year"]\n\n'
            f"Question: How does photosynthesis work?\n"
            f'Output: ["photosynthesis process explained", "how plants convert sunlight", "chlorophyll light energy conversion"]\n\n'
            f"### YOUR TURN\n"
            f"Question: {user_question}\n"
            f"Output: ["
        )

    def _instPrompt_EN(self, context: str, user_question: str) -> str:
        return (
            f"### ROLE\n"
            f"You are a document assistant. Your only job is to answer questions "
            f"using the provided sources.\n\n"
            f"### STRICT OUTPUT RULES\n"
            f"- Use ONLY the sources below. Never use outside knowledge.\n"
            f"- Output the final answer IMMEDIATELY. Do not analyze, plan, or think out loud.\n"
            f"- No reasoning steps. No thought process. No <think>, <|channel>, or similar tags.\n"
            f"- If the answer is not found in the sources, reply exactly: "
            f"'{self._errSources_EN()}'\n"
            f"- Always end with 'Source:' followed by the source name(s) used.\n\n"
            f"### SOURCES\n"
            f"{context}\n\n"
            f"### QUESTION\n"
            f"{user_question}\n\n"
            f"### FINAL ANSWER (no preamble, start answering immediately)\n"
        )

    def _errSources_EN(self) -> str:
        return "Information not found within provided data."

    # ── Portuguese ────────────────────────────────────────────────────────────

    def _instQueries_PTBR(self, n_queries: int, user_question: str) -> str:
        return (
            f"### TAREFA\n"
            f"Gere exatamente {n_queries} consultas de pesquisa curtas para encontrar "
            f"informações que respondam a pergunta abaixo.\n\n"
            f"### REGRAS DE SAÍDA\n"
            f"- Retorne APENAS um array JSON puro de strings.\n"
            f"- Nenhum texto antes ou depois do array.\n"
            f"- Sem explicações, sem raciocínio, sem processo de pensamento.\n"
            f"- Cada consulta deve ter 5-10 palavras.\n\n"
            f"### EXEMPLOS\n"
            f"Pergunta: O que são os impostos no Brasil em 2024?\n"
            f'Saída: ["impostos Brasil 2024", "alíquotas imposto de renda", "tabela fiscal ano atual"]\n\n'
            f"Pergunta: Como funciona a fotossíntese?\n"
            f'Saída: ["processo fotossíntese explicado", "como plantas convertem luz solar", "conversão energia clorofila"]\n\n'
            f"### SUA VEZ\n"
            f"Pergunta: {user_question}\n"
            f"Saída: ["
        )

    def _instPrompt_PTBR(self, context: str, user_question: str) -> str:
        return (
            f"### FUNÇÃO\n"
            f"Você é um assistente de documentos. Seu único trabalho é responder "
            f"perguntas usando as fontes fornecidas.\n\n"
            f"### REGRAS DE SAÍDA\n"
            f"- Use APENAS as fontes abaixo. Nunca use conhecimento externo.\n"
            f"- Escreva a resposta final IMEDIATAMENTE. Não analise, planeje ou pense em voz alta.\n"
            f"- Sem etapas de raciocínio. Sem processo de pensamento. Sem tags <think>, <|channel> ou similares.\n"
            f"- Se a resposta não estiver nas fontes, responda exatamente: "
            f"'{self._errSources_PTBR()}'\n"
            f"- Sempre termine com 'Fontes:' seguido do(s) nome(s) da(s) fonte(s) utilizada(s).\n\n"
            f"### FONTES\n"
            f"{context}\n\n"
            f"### PERGUNTA\n"
            f"{user_question}\n\n"
            f"### RESPOSTA FINAL (sem preâmbulo, comece a responder imediatamente)\n"
        )

    def _errSources_PTBR(self) -> str:
        return "Nenhuma informação encontrada."