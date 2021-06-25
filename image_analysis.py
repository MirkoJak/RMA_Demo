import streamlit as st
import fitz
import os
import sys
import pandas as pd
from google.cloud import vision
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


@st.cache(hash_funcs={"builtins.SwigPyObject": lambda _: None}, show_spinner=False)
def _extract_images_from_pdf(pdf_file):
    # opening the file
    pdf_file = fitz.open(pdf_file.name, stream=pdf_file.getvalue())

    # finding number of pages in the pdf
    number_of_pages = len(pdf_file)

    images = []
    # iterating through each page in the pdf
    for current_page_index in range(number_of_pages):
        # iterating through each image in every page of PDF
        for img_index, img in enumerate(pdf_file.getPageImageList(current_page_index)):
            xref = img[0]
            image = fitz.Pixmap(pdf_file, xref)
            #  if it is CMYK: convert to RGB first
            if image.n >= 5:
                image = fitz.Pixmap(fitz.csRGB, image)
            images.append(image.tobytes())

    return images


@st.cache(show_spinner=False)
def _classify_image(image_bytes):
    # Convert the image
    image = vision.Image(content=image_bytes)

    # Instantiates a client
    credentials = service_account.Credentials.from_service_account_info(credentials_info)
    client = vision.ImageAnnotatorClient(credentials=credentials)

    # Call the API
    response = client.label_detection(image=image)
    print('Warning: Vision API call')
    sys.stdout.flush()
    sess = SessionState.get(api_calls=0)
    sess.api_calls = sess.api_calls + 1
    labels = response.label_annotations

    descriptions = [l.description for l in labels]
    scores = [l.score for l in labels]

    return dict(zip(descriptions, scores))


@st.cache(show_spinner=False)
def _select_labels(labels):
    # Filtro solo le label con score maggiore di 0.7 e che appartengono ad un gruppo prescelto
    selected_labels = []
    translation = {'Bathroom': 'Bagno',
                   'Bedrock': 'Basamento',
                   'Building': 'Edificio',
                   'Building material': 'Materiale da costruzione',
                   'Ceiling': 'Soffitto',
                   'Floor': 'Pavimento',
                   'Flooring': 'Pavimentazione',
                   'House': 'Abitazione',
                   'Plaster': 'Intonaco',
                   'Plumbing': 'Tubature',
                   'Plumbing fixture': 'Impianto idraulico',
                   'Toilet': 'Gabinetto',
                   'Window': 'Finestra'}
    for label, score in labels.items():
        if score > 0.7 and label in translation.keys():
            selected_labels.append((translation[label], score))
    return dict(selected_labels)


@st.cache(hash_funcs={"builtins.SwigPyObject": lambda _: None}, show_spinner=False)
def image_analysis(file):
    if file.type == 'application/pdf':
        # Estraggo le immagini dal pdf
        images = _extract_images_from_pdf(file)
    elif file.type == 'image/png' or file.type == 'image/jpeg':
        images = [file.read()]

    out = {}
    for i, im in enumerate(images):
        # Controllo prima se le label sono già presenti in formato csv nella temporary
        filename = os.path.splitext(os.path.basename(file.name))[0] + '_' + str(file.size) + '_' + str(i + 1) + '.csv'
        if os.path.exists(os.path.join(r'tmp/image_labels', filename)):
            out[i + 1] = (im, pd.read_csv(os.path.join(r'tmp/image_labels', filename),
                                          header=0, names=['Label', 'Confidence']).set_index('Label').
                          to_dict()['Confidence'])
        else:
            # Classifico l'immagine con le API e salvo le label in csv
            labels = _classify_image(im)
            selected_labels = _select_labels(labels)
            out[i + 1] = (im, selected_labels)
            if not os.path.exists(r'tmp/image_labels'):
                os.mkdir(r'tmp/image_labels')
            pd.DataFrame(selected_labels.values(), index=selected_labels.keys(), columns=['Confidence']). \
                to_csv(os.path.join(r'tmp/image_labels', filename))

    return out
