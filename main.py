import streamlit as st
import pandas as pd
from text_analysis import text_analysis
from image_analysis import image_analysis
from invoice_analysis import invoice_analysis

# -----Sidebar----- #
st.sidebar.image(r'figures/MicrosoftTeams-image.png', width=225)
st.sidebar.title('AI per la Polizza Globale Fabbricati')

st.sidebar.subheader("Carica i file")
uploaded_file_1 = st.sidebar.file_uploader("Carica il testo della denuncia", type=['pdf', 'txt'])
uploaded_file_2 = st.sidebar.file_uploader("Carica le foto dell'evento", type=['pdf', 'jpg', 'png'])
uploaded_file_3 = st.sidebar.file_uploader("Carica il documento di fattura/preventivo", type=['pdf', 'txt'])

st.sidebar.markdown(
    "<h5 style='text-align: center; color: black;'>si consiglia refresh del browser ad ogni nuovo file testato ("
    "pulizia cache)</h4>",
    unsafe_allow_html=True)


# -----Page----- #
col1, col2, col3 = st.beta_columns(3)
title1 = col1.empty()
title2 = col2.empty()
title3 = col3.empty()

# Nella prima colonna gestisco l'estrazione dei dati da file testuali
if uploaded_file_1 is None:
    title1.subheader('Carica il testo della denuncia per estrarre i dati chiave')

else:
    title1.subheader('Dati chiave trovati nel testo')

    # Estraggo le info chiave
    key_data = text_analysis(uploaded_file_1)

    # Mostro i risultati
    col1.dataframe(pd.DataFrame(key_data.values(), index=key_data.keys(), columns=['Valori trovati']))

# Nella seconda colonna gestisco l'estrazione dei dati da file immagine
if uploaded_file_2 is None:
    title2.subheader('Carica le immagini dell\'evento per determinarne il contenuto')

else:
    title2.subheader('Contenuto delle immagini')

    results = image_analysis(uploaded_file_2)
    if len(results) > 1:
        option = col2.selectbox('Quale immagine vuoi visualizzare?', options=list(results.keys()))
    else:
        option = 1

    if option is not None:
        im = results[option][0]
        labels = results[option][1]
        col2.image(im)
        col2.dataframe(pd.DataFrame(labels.values(), index=labels.keys(), columns=['Confidence']).
                       sort_values('Confidence', ascending=False))

# Nella terza colonna gestisco l'estrazione dei dati da file testuali
if uploaded_file_3 is None:
    title3.subheader('Carica il testo della fattura o del preventivo')

else:
    title3.subheader('Importo stimato')

    # Estraggo le info chiave
    key_data = invoice_analysis(uploaded_file_3)

    # Mostro i risultati
    col3.dataframe(pd.DataFrame(key_data.values(), index=key_data.keys(), columns=['Valori trovati']))

