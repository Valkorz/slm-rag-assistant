# SLM-RAG-ASSISTANT

This project implements a Small Language Model interface that uses RAG (Retrieval Augmented Generation) to extract data from a ChromaDB database based on context. 

---

## 💻 Setup

This project was created using `Python 3.12.6` and a list of libraries disclosed within `requirements.txt`. The small-language-models used were downloaded and hosted locally using `LMStudio`. The following steps are necessary to execute this project:

1. **Install LMStudio**

    [LMStudio](https://lmstudio.ai/) is a free tool for running small to large language models locally, allowing the prompting to be done through a built-in interface or through user-defined endpoints.

2. **Download the Small Language Models**

    From within the LMStudio interface, download the following models:
    - `meta-llama-3.1-8b-instruct`
    - `deepseek-r1-distill-qwen-1.5b`

    Alternatively, for a broader language support, you can use these models:
    - `google/gemma-4-e2b`
    - `google/gemma-4-e4b`

    The following image illustrates the download procedure:
    ![LMStudio model download interface using huggingface](docs/images/lmstudio-modeldownload.png)

3. **Install required libraries**

    This project uses several libraries, ranging from `openai` for endpoint communication to `chromadb` for context window management.
    Open the terminal within the project folder and execute the following command:
    ```
        pip install -r requirements.txt 
    ```
    This will install all necessary dependencies explicitly stated within the requirements file.
    These are the required libraries:
    ```
        chromadb>=0.5.23
        sentence-transformers>=3.2.1
        pymupdf>=1.27.2.2
        langchain_text_splitters>=1.1.1
        openai>=2.24.0
        pillow>=11.2.1
    ```
4. **Initiate the local hosting of a language model**
    For the model usage, you must load the necessary models and start the server. The application's interface makes this task simple. Please refer to the following image:
    ![LMStudio model loading](docs/images/lmstudio-modelloading.png)

5. **Interface initialization and usage**
    To execute the project, you must ensure you have Python at version `3.12.6` or above, then simply execute the `assistant.py` script, which initiates a TKinter window. 
    Inside the running instance, the user is able to select documents from the desktop, change the model's language and perform a question, which will be answered by the model based on the contents found within the source files. 
    The first initialization may take a while.
    **IMPORTANT: the LMStudio server MUST be running with both models loaded and active.**
    The following image showcases an usage example for the assistant.

    ![Application instance](docs/images/assistant.png)

    The picture shows the TKinter interface being executed. The user has selected a document named: `Uncertainty_principle....pdf`, and asked the following question: "What does the wave of a particle have to do with the uncertainty principle?". After roughly 1 minute and 30 seconds, the assistant read the PDF, chunkized it into the database and provided a matching chunk as a response. The model did not invent anything as the response is exactly as present inside the source material:

    ![Source material](docs/images/source-material.png)

6. **Perform a headless prompt**
    You can also perform a headless prompt by running the following command inside the terminal (while accessing the project folder): 

    ```python prompt_assistant.py -f [list_of_file_paths] -q "question"```

---

## ⚙️ Hardware

The hardware used during the development of this project contains the following specifications:

- **GPU:** RTX 2050 (4GB RAM)
- **CPU:** Intel I5-12450H 
- **RAM:** 16 GB DDR5
- **STORAGE:** 1TB SSD

---

## 💡 Purpose of this project

Text processing and analysis is one of the cornerstone applications of language models, however, adopting privately hosted Large Language Models (LLMs) for this task brings forth relevant privacy concerns. How can we ensure our data is being processed in a secure and private manner whilst being decoupled from a private ecossystem?
This project addresses these concerns by leveraging small language models (SLMs) with local deployment, ensuring data remains under user control. For comprehensive insights into LLM privacy risks, see [Beyond Data Privacy: New Privacy Risks for Large Language Models](https://doi.org/10.1145/3605764.3623951) by Du, Li, Li, and Ding (Purdue University).

This project was implemented with consumer-grade hardware in mind, ensuring that language models will run cheaply and quickly on less capable devices, while mitigating the common issues (eg. hallucinations) by using **Retrieval Augmented Generation (RAG)** to ensure consistent and trustworthy responses.


