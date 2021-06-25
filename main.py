import streamlit as st
import pandas as pd
from text_analysis import text_analysis
from image_analysis import image_analysis
from invoice_analysis import invoice_analysis
import SessionState

# -----Sidebar----- #
st.sidebar.image(r'figures/MicrosoftTeams-image.png', width=225)
st.sidebar.title('AI per la Polizza Globale Fabbricati')

st.sidebar.subheader("Carica i file")
uploaded_file_1 = st.sidebar.file_uploader("Carica il testo della denuncia", type=['pdf', 'txt'])
uploaded_file_2 = st.sidebar.file_uploader("Carica le foto dell'evento", type=['pdf', 'jpg', 'png'])
uploaded_file_3 = st.sidebar.file_uploader("Carica il documento di fattura/preventivo", type=['pdf', 'txt'])

api_calls = st.sidebar.empty()
api_calls.text('API Calls: '+str(SessionState.get(api_calls=0).api_calls))
st.sidebar.markdown(
    "<h5 style='text-align: center; color: black;'>si consiglia refresh del browser ad ogni nuovo file testato ("
    "pulizia cache)</h4>",
    unsafe_allow_html=True)


# -----Page----- #

# Nella prima colonna gestisco l'estrazione dei dati da file testuali
if uploaded_file_1 is None:
    st.subheader('Carica il testo della denuncia per estrarre i dati chiave')

else:
    st.subheader('Dati chiave trovati nel testo')

    # Estraggo le info chiave
    key_data = text_analysis(uploaded_file_1)
    api_calls.text('API Calls: ' + str(SessionState.get(api_calls=0).api_calls))

    # Mostro i risultati
    st.dataframe(pd.DataFrame(key_data.values(), index=key_data.keys(), columns=['Valori trovati']))

# Nella seconda colonna gestisco l'estrazione dei dati da file immagine
if uploaded_file_2 is None:
    st.subheader('Carica le immagini dell\'evento per determinarne il contenuto')

else:
    st.subheader('Contenuto delle immagini')

    # Classifico le immagini
    results = image_analysis(uploaded_file_2)
    api_calls.text('API Calls: ' + str(SessionState.get(api_calls=0).api_calls))

    # Mostro i risultati
    if len(results) > 1:
        option = st.selectbox('Quale immagine vuoi visualizzare?', options=list(results.keys()))
    else:
        option = 1

    if option is not None:
        im = results[option][0]
        labels = results[option][1]
        st.image(im, width=255)
        st.dataframe(pd.DataFrame(labels.values(), index=labels.keys(), columns=['Confidence']).
                       sort_values('Confidence', ascending=False))

# Nella terza colonna gestisco l'estrazione dei dati da file testuali
if uploaded_file_3 is None:
    st.subheader('Carica il testo della fattura o del preventivo')

else:
    st.subheader('Importo stimato')

    # Estraggo le info chiave
    key_data = invoice_analysis(uploaded_file_3)
    api_calls.text('API Calls: ' + str(SessionState.get(api_calls=0).api_calls))

    # Mostro i risultati
    st.dataframe(pd.DataFrame(key_data.values(), index=key_data.keys(), columns=['Valori trovati']))

