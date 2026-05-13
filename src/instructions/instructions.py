# This class is used to define different instructions for different languages
class Instructions:
    _language: str
    _mode: str  # "document" | "financial"

    def __init__(self, lang: str, mode: str = "document"):
        self._language = lang
        self._mode = mode

    def set_language(self, lang : str):
        languages = ["EN", "PTBR"]
        if not languages.__contains__(lang):
            pass
        self._language = lang

    def set_mode(self, mode: str):
        modes = ["document", "financial"]
        if mode in modes:
            self._mode = mode

    def get_queryInstruction(self, n_queries: int, user_question: str) -> str:
        if self._language.upper() == "EN":
            return self._instQueries_EN(n_queries, user_question)
        elif self._language.upper() == "PTBR":
            return self._instQueries_PTBR(n_queries, user_question)
        else:
            return "AN ERROR OCCURED WITH THE REQUEST. PLEASE REPORT THIS."

    def get_promptInstruction(self, context: str, user_question: str) -> str:
        lang = self._language.upper()
        if self._mode == "financial":
            if lang == "EN":
                return self._instPrompt_financial_EN(context, user_question)
            elif lang == "PTBR":
                return self._instPrompt_financial_PTBR(context, user_question)
        else:
            if lang == "EN":
                return self._instPrompt_EN(context, user_question)
            elif lang == "PTBR":
                return self._instPrompt_PTBR(context, user_question)
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
            f"### CRITICAL LANGUAGE RULE\n"
            f"ALL queries MUST be written in ENGLISH. "
            f"No Spanish, Portuguese, French, or any other language. ENGLISH ONLY.\n\n"
            f"### OUTPUT FORMAT\n"
            f"Respond ONLY with a JSON object in this exact format:\n"
            f"{{\n"
            f'  "queries": ["query 1", "query 2", "query 3"],\n'
            f'  "thought_process": "brief explanation of why you chose these queries"\n'
            f"}}\n\n"
            f"### QUERY RULES\n"
            f"- Each query must be 5-10 words.\n"
            f"- Queries must be meaningfully different from each other.\n"
            f"- Focus on the core concepts in the question, not the exact words.\n\n"
            f"### EXAMPLE\n"
            f"Question: What are the tax brackets for 2024?\n"
            f"{{\n"
            f'  "queries": ["income tax brackets 2024 rates", "federal tax table thresholds", "IRS progressive tax bands"],\n'
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

    def _instPrompt_financial_EN(self, context: str, user_question: str) -> str:
        return (
            f"### ROLE\n"
            f"You are a tax consultant. Answer questions based on the provided sources, "
            f"applying reasoning, calculations, and inferences from the data found.\n\n"
            f"### OUTPUT FORMAT\n"
            f"Respond ONLY with a JSON object in this exact format:\n"
            f"{{\n"
            f'  "answer": "your final answer here",\n'
            f'  "sources": ["Source name p.X", "Source name p.Y"],\n'
            f'  "thought_process": "your internal reasoning about which sources were used"\n'
            f"}}\n\n"
            f"### ANSWER RULES\n"
            f"- Base your answer EXCLUSIVELY on information from the sources below.\n"
            f"- YOU MUST reason, calculate, and infer from the source data "
            f"(e.g., apply tax bracket tables, calculate tax owed for a specific income, "
            f"deduce consequences of tax rules).\n"
            f"- Use '{self._errSources_EN()}' ONLY if the TOPIC does not appear in any source. "
            f"If the sources contain data that allows answering through reasoning, answer using that data.\n"
            f"- The 'answer' field must be direct and complete — include the calculation or deduction when relevant.\n"
            f"- The 'sources' field must list every source consulted.\n"
            f"- The 'thought_process' field is for your internal reasoning only — it will not be shown to the user.\n\n"
            f"### EXAMPLE\n"
            f"Sources: [Source 1 | table.pdf p.3] Bracket $44,726 to $95,375: rate 22%, deduction $5,147\n"
            f"Question: If I earn $60,000, how much income tax do I owe?\n"
            f"{{\n"
            f'  "answer": "With income of $60,000, you fall in the 22% bracket. '
            f'Tax: $60,000 × 22% = $13,200, minus the $5,147 deduction = $8,053 owed.",\n'
            f'  "sources": ["table.pdf p.3"],\n'
            f'  "thought_process": "$60,000 falls in the $44,726–$95,375 bracket (22%). Applied rate and subtracted fixed deduction."\n'
            f"}}\n\n"
            f"### SOURCES\n"
            f"{context}\n\n"
            f"### QUESTION\n"
            f"{user_question}\n\n"
            f"{{"
        )

    # ── Portuguese ────────────────────────────────────────────────────────────

    def _instQueries_PTBR(self, n_queries: int, user_question: str) -> str:
        return (
            f"### TAREFA\n"
            f"Gere exatamente {n_queries} consultas de pesquisa curtas para encontrar "
            f"informações que respondam a pergunta abaixo.\n\n"
            f"### REGRA CRÍTICA DE IDIOMA\n"
            f"TODAS as consultas DEVEM ser escritas em PORTUGUÊS DO BRASIL. "
            f"Nenhum espanhol, inglês, francês ou qualquer outro idioma. SOMENTE PORTUGUÊS.\n\n"
            f"### FORMATO DE SAÍDA\n"
            f"Responda APENAS com um objeto JSON neste formato exato:\n"
            f"{{\n"
            f'  "queries": ["consulta 1", "consulta 2", "consulta 3"],\n'
            f'  "thought_process": "breve explicação de por que você escolheu essas consultas"\n'
            f"}}\n\n"
            f"### REGRAS DAS CONSULTAS\n"
            f"- Cada consulta deve ter 5-10 palavras.\n"
            f"- As consultas devem ser significativamente diferentes entre si.\n"
            f"- Foque nos conceitos centrais da pergunta, não nas palavras exatas.\n\n"
            f"### EXEMPLO\n"
            f"Pergunta: O que são os impostos no Brasil em 2024?\n"
            f"{{\n"
            f'  "queries": ["impostos brasileiros 2024 tipos alíquotas", "tabela imposto renda pessoa física", "obrigações tributárias contribuinte Brasil"],\n'
            f'  "thought_process": "Busquei pelos impostos diretamente, depois pelas alíquotas e por fim pelas obrigações do contribuinte."\n'
            f"}}\n\n"
            f"### SUA VEZ\n"
            f"Pergunta: {user_question}\n"
            f"{{"
        )
    

    def _instPrompt_financial_PTBR(self, context: str, user_question: str) -> str:
        return (
            f"### FUNÇÃO\n"
            f"Você é um consultor tributário. Responda perguntas com base nas fontes fornecidas, "
            f"aplicando raciocínio, cálculos e inferências a partir dos dados encontrados.\n\n"
            f"### FORMATO DE SAÍDA\n"
            f"Responda APENAS com um objeto JSON neste formato exato:\n"
            f"{{\n"
            f'  "answer": "sua resposta final aqui",\n'
            f'  "sources": ["Nome da fonte p.X", "Nome da fonte p.Y"],\n'
            f'  "thought_process": "seu raciocínio interno sobre quais fontes foram usadas"\n'
            f"}}\n\n"
            f"### REGRAS DA RESPOSTA\n"
            f"- Baseie sua resposta EXCLUSIVAMENTE nas informações das fontes abaixo.\n"
            f"- VOCÊ DEVE raciocinar, calcular e inferir a partir dos dados das fontes "
            f"(ex: aplicar tabelas de alíquotas, calcular imposto sobre um valor específico, "
            f"deduzir consequências de regras tributárias).\n"
            f"- Use '{self._errSources_PTBR()}' SOMENTE se o ASSUNTO não aparecer em nenhuma fonte. "
            f"Se as fontes contêm dados que permitem responder com raciocínio, responda usando esses dados.\n"
            f"- O campo 'answer' deve ser direto e completo — inclua o cálculo ou dedução quando relevante.\n"
            f"- O campo 'sources' deve listar todas as fontes consultadas.\n"
            f"- O campo 'thought_process' é para seu raciocínio interno — não será exibido ao usuário.\n\n"
            f"### EXEMPLO\n"
            f"Fontes: [Fonte 1 | tabela.pdf p.3] Faixa de R$2.826,66 a R$3.751,05: alíquota 15%, dedução R$354,80\n"
            f"Pergunta: Se eu recebo R$ 3.500, quanto pago de IR?\n"
            f"{{\n"
            f'  "answer": "Com renda de R$3.500,00, você está na faixa de 15%. '
            f'O imposto é: R$3.500,00 × 15% = R$525,00, menos a dedução de R$354,80 = R$170,20 de IR mensal.",\n'
            f'  "sources": ["tabela.pdf p.3"],\n'
            f'  "thought_process": "O valor R$3.500 cai na faixa R$2.826,66–R$3.751,05 (15%). Apliquei alíquota e deduzi o valor fixo."\n'
            f"}}\n\n"
            f"### FONTES\n"
            f"{context}\n\n"
            f"### PERGUNTA\n"
            f"{user_question}\n\n"
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