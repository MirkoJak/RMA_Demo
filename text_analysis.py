import streamlit as st
import os
import io
import re
import sys
import dateutil.parser as dparser
from datetime import datetime
from google.cloud import documentai
from google.oauth2 import service_account

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
    print('Warning: Document AI API call')
    sys.stdout.flush()
    result = client.process_document(request=request)
    document = result.document

    return document.text.splitlines(keepends=True)


@st.cache(show_spinner=False)
def _extract_polizza(lines):
    # Cerco prima i casi che rispettano il pattern preciso
    polizza_l = [re.search(r"(?:\b|n|n\.|n°|#)\d{4}(?:\\|/|-)\d{2}(?:\\|/|-)\d{7}\b", l.lower()) for l in lines]
    polizza_l = [e.group() for e in polizza_l if e is not None]
    # Se non trovo niente, provo a cercare le stringhe numeriche in prossimità della parola polizza
    if len(polizza_l) == 0:
        text = ' '.join(lines).replace('\n', '')
        iterator = re.finditer(r'(?:\b|n|n\.|n°|#)(\d{7,}|\d{2}(?:\\|/|-)\d{5,})\b', text.lower())
        for match in iterator:
            prev = (match.start() - 15 if (match.start() - 15) > 0 else 0)
            if 'polizza' in text[prev:match.start()].lower():
                polizza_l.append(match.group())

    if len(polizza_l) > 0:
        return polizza_l[0]
    else:
        return ''


@st.cache(show_spinner=False)
def _extract_data_evento(lines):
    text = ' '.join(lines).replace('\n', '')
    date_l = []
    # Trovo le date che rispettano un certo formato
    iterator = re.finditer(r'\b(0[1-9]|1[0-9]|2[0-9]|3[01]|(?:19|20)\d{2})[\s\-\\\/\.]{1,3}(0[1-9]|1['
                           r'012]|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre'
                           r'|dicembre|gen\.*|feb\.*|mar\.*|apr\.*|mag\.*|giu\.*|lug\.*|ago\.*|set\.*|ott\.*|nov\.*|dic'
                           r'\.*)[\s\-\\\/\.]{0,3}((?:19|20)?\d{2})?\b', text.lower())
    for match in iterator:
        valid = True
        # Traduco i mesi in inglese per un corretto parsing
        matched_date = match.group()
        matched_date = re.sub(r'gennaio|gen', 'jan', matched_date)
        matched_date = re.sub(r'febbraio|feb', 'feb', matched_date)
        matched_date = re.sub(r'marzo|mar', 'mar', matched_date)
        matched_date = re.sub(r'aprile|apr', 'apr', matched_date)
        matched_date = re.sub(r'maggio|mag', 'may', matched_date)
        matched_date = re.sub(r'giugno|giu', 'jun', matched_date)
        matched_date = re.sub(r'luglio|lug', 'jul', matched_date)
        matched_date = re.sub(r'agosto|ago', 'aug', matched_date)
        matched_date = re.sub(r'settembre|set', 'sep', matched_date)
        matched_date = re.sub(r'ottobre|ott', 'oct', matched_date)
        matched_date = re.sub(r'novembre|nov', 'nov', matched_date)
        matched_date = re.sub(r'dicembre|dic', 'dec', matched_date)
        # Scarto le date che non riesco a parsare o che non hanno un anno valido
        try:
            parsed_date = dparser.parse(matched_date)
            if not (datetime.now().year - 20 <= parsed_date.year <= datetime.now().year):
                valid = False
        except:
            valid = False

        # Se la data è vicino ad una parola chiave, la considero con priorità maggiore
        if valid:
            prev = (match.start() - 20 if (match.start() - 20) > 0 else 0)
            succ = (match.end() + 20 if (match.end() + 20) < len(text) else len(text))
            keywords = r'data evento|avvenut|sinistro|accadut|verificat'
            if re.search(keywords, text[prev:match.start()].lower()) or re.search(keywords,
                                                                                  text[match.end():succ].lower()):
                score = 1
            else:
                score = 0

            date_l.append((parsed_date, score))

    # Ordino per score
    date_l.sort(key=lambda tup: tup[1], reverse=True)

    if len(date_l) > 0:
        return date_l[0]
    else:
        return ''


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
def _extract_email(lines):
    email_l = [re.search(r'\b[\w.-]+?@\w+?\.\w+?\b', l) for l in lines]
    # Escludo l'email del gruppo RealeMutua
    keywords = r'realemutua|reale|sinistr|assicurazion|polizz|insurance'
    email_l = [e.group() for e in email_l if e is not None and re.search(keywords, e.group().lower()) is None]

    if len(email_l) > 0:
        return email_l[0]
    else:
        return ''


@st.cache(show_spinner=False)
def _extract_category(lines):
    # Assegno uno score ad ogni categoria di evento in base ad un vocabolario predefinito
    vocabulary = {'Acqua condotta': r'\b(acqua|rottur.|tubazion.|idraulic.|infiltrazion.|fuoriuscit.|perdit.|idric'
                                    r'.|occlusion.|colonna montante|scarico|ostruzion.)\b',
                  'Evento atmosferico': r'\b(vent.|pioggia|diluvio|precipitazion.|nev.|nevicat.|fulmin.|tuon.)\b',
                  'Fenomeno elettrico': r'\b(elettric.|corto circuit.|circuit.|impedenz.|corrent.|cav.|tension'
                                        r'.|alimentator.|elettricit.|contator.|blackout)\b',
                  'Incendio': r'\b(fiamm.|fuoco|incendi.?|caldo|calore|esplosion.|divampat.|bruciat.)\b',
                  'Evento socio politico': r'\b(manifestazion.|imbrattato|vandalismo)\b',
                  'Guasto ladro': r'\b(ladr.|furt.|scassinat.|manomess.|serratur.|intrusion.|rubat.|rubare|sottratt'
                                  r'.|forzat.)\b',
                  'Cristallo': r'\b(cristall.)\b'}
    text = ' '.join(lines).lower().replace('\n', '')
    classes = []
    for category, regex in vocabulary.items():
        classes.append((category, len(re.findall(regex, text))))
    classes.sort(key=lambda tup: tup[1], reverse=True)

    return classes[0][0]


@st.cache(show_spinner=False)
def _read_data_from_text(lines):
    # Estraggo il numero polizza
    polizza = _extract_polizza(lines)

    # Estraggo la data evento
    data_evento = _extract_data_evento(lines)

    # Estraggo il CF
    cf = _extract_cf(lines)

    # Estraggo la P.IVA
    iva = _extract_iva(lines)

    # Estraggo l'email
    email = _extract_email(lines)

    # Estraggo la causale
    cat = _extract_category(lines)

    # Preparo l'output
    if isinstance(data_evento, tuple):
        if data_evento[1] == 1:
            data_evento_label = 'Data evento'
        else:
            data_evento_label = 'Data'
        data_evento_value = data_evento[0].strftime('%d-%m-%Y')
    else:
        data_evento_label = 'Data evento'
        data_evento_value = ''

    return {'Numero polizza': polizza,
            data_evento_label: data_evento_value,
            'Codice Fiscale': cf,
            'Partita IVA': iva,
            'Email': email,
            'Causale': cat}


@st.cache(show_spinner=False)
def text_analysis(file):
    if file.type == 'text/plain':
        # Leggo il file come stringa
        stringio = io.StringIO(file.getvalue().decode("utf-8"))
        doc = stringio.readlines()
    elif file.type == 'application/pdf':
        # Controllo prima se il file non è già presente in formato text nella temporary
        filename = os.path.splitext(os.path.basename(file.name))[0] + '.txt'
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
