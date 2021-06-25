import streamlit as st
import re
import io
import os
import sys
from price_parser import Price
from google.cloud import documentai
from google.oauth2 import service_account
import SessionState

# Secrets
credentials_info = {'type': st.secrets['type'],
                    'project_id': st.secrets['project_id'],
                    'private_key_id': st.secrets['private_key_id'],
                    'private_key': st.secrets['private_key'],
                    'client_email': st.secrets['client_email'],
                    'client_id': st.secrets['client_id'],
                    'auth_uri': st.secrets['auth_uri'],
                    'token_uri': st.secrets['token_uri'],
                    'auth_provider_x509_cert_url': st.secrets['auth_provider_x509_cert_url'],
                    'client_x509_cert_url': st.secrets['client_x509_cert_url']}
project_id = st.secrets['project_id']
location = st.secrets['location']
processor_id = st.secrets['processor_id']


@st.cache(show_spinner=False)
def _read_text_from_pdf(pdf_file):
    # Read the file into memory
    content = pdf_file.read()
    document = {"content": content, "mime_type": pdf_file.type}

    # Configure client
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    opts = {}
    if location == "eu":
        opts = {"api_endpoint": "eu-documentai.googleapis.com"}
    client = documentai.DocumentProcessorServiceClient(client_options=opts, credentials=credentials)

    # Configure the process request
    name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"
    request = {"name": name, "raw_document": document}

    # Call the API
    result = client.process_document(request=request)
    print('Warning: Document AI API call')
    sys.stdout.flush()
    sess = SessionState.get(api_calls=0)
    sess.api_calls = sess.api_calls + 1
    document = result.document

    return document.text.splitlines(keepends=True)


@st.cache(show_spinner=False)
def _extract_cf(lines):
    cf_l = [re.search(
        r"\b(?:[A-Z][AEIOU][AEIOUX]|[B-DF-HJ-NP-TV-Z]{2}[A-Z]){2}(?:[\dLMNP-V]{2}(?:[A-EHLMPR-T](?:[04LQ][1-9MNP-V]|["
        r"15MR][\dLMNP-V]|[26NS][0-8LMNP-U])|[DHPS][37PT][0L]|[ACELMRT][37PT][01LM]|[AC-EHLMPR-T][26NS][9V])|(?:["
        r"02468LNQSU][048LQU]|[13579MPRTV][26NS])B[26NS][9V])(?:[A-MZ][1-9MNP-V][\dLMNP-V]{2}|[A-M][0L](?:[1-9MNP-V]["
        r"\dLMNP-V]|[0L][1-9MNP-V]))[A-Z]\b",
        l) for l in lines]
    cf_l = [e.group() for e in cf_l if e is not None]

    if len(cf_l) > 0:
        return cf_l[0]
    else:
        return ''


@st.cache(show_spinner=False)
def _extract_iva(lines):
    text = ' '.join(lines).replace('\n','')
    iva_l = []
    iterator = re.finditer(r"\b\d{11}\b", text.lower())

    # Do maggiore priorità a quei codici vicini a parole chiave (iva)
    for match in iterator:
        prev = (match.start() - 10 if (match.start() - 10) > 0 else 0)
        if re.search(r'\biva\b', text[prev:match.start()].lower()):
            score = 1
        else:
            score = 0
        iva_l.append((match.group(), score))

        # Ordino per score
    iva_l.sort(key=lambda tup: tup[1], reverse=True)

    if len(iva_l) > 0:
        return iva_l[0][0]
    else:
        return ''


@st.cache(show_spinner=False)
def _extract_price(lines):
    # Estraggo gli importi in € dal testo
    text = ' '.join(lines).lower().replace('\n', '')
    keywords = r'\b(totale|finale|liquidazione|liquidato|indennizzo)\b'
    iterator = re.finditer(
        r'(?:^|\s)((?:€|euro)\s?\d+(?:,\d+|\.\d+)*[.,]?\d*|\d+(?:,\d+|\.\d+)*[.,]?\d*\s?(?:€|euro))(?:$|\s)', text)
    prices = []
    for match in iterator:
        p = Price.fromstring(re.sub(r'€|euro', '', match.group()).strip()).amount_float
        # Do uno score maggiore a quei prezzi icino a determinate keyword
        prev = match.start() - 30 if (match.start() - 30) > 0 else 0
        succ = match.end() + 30 if (match.end() + 30) < len(text) else len(text)
        if re.search(keywords, text[prev:match.start()]) or re.search(keywords, text[match.end():succ]):
            score = 1
        else:
            score = 0
        prices.append((p, score))

    # Prendo il valore massimo di quelli con score 1 (se non ci sono con score 1 prendo il massimo con score 0)
    prices.sort(key=lambda tup: (tup[1], tup[0]), reverse=True)
    p_max = prices[0][0]
    return p_max


@st.cache(show_spinner=False)
def _read_data_from_text(lines):

    # Estraggo il CF
    cf = _extract_cf(lines)

    # Estraggo la P.IVA
    iva = _extract_iva(lines)

    # Estraggo l'importo'
    price = _extract_price(lines)

    return {'Codice Fiscale': cf,
            'Partita IVA': iva,
            'Importo': price}


@st.cache(show_spinner=False)
def invoice_analysis(file):
    if file.type == 'text/plain':
        # Leggo il file come stringa
        stringio = io.StringIO(file.getvalue().decode("utf-8"))
        doc = stringio.readlines()
    elif file.type == 'application/pdf':
        # Controllo prima se il file non è già presente in formato text nella temporary
        filename = os.path.splitext(os.path.basename(file.name))[0] + '_' + str(file.size) + '.txt'
        if os.path.exists(os.path.join(r'tmp/text', filename)):
            with open(os.path.join(r'tmp/text', filename), 'r', encoding='utf-8') as f:
                doc = f.readlines()
        else:
            # Uso le API Google per estrarre il testo dal file e lo salvo
            doc = _read_text_from_pdf(file)
            if not os.path.exists(r'tmp/text'):
                os.mkdir(r'tmp/text')
            with open(os.path.join(r'tmp/text', filename), "w", encoding='utf-8') as f:
                f.writelines(doc)

    # Estraggo i dati chiave
    key_data = _read_data_from_text(doc)

    return key_data
