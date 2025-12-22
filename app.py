import streamlit as st
import edge_tts
import asyncio
import io
import re
from datetime import datetime
from deep_translator import GoogleTranslator

# --- Configuración de Página ---
st.set_page_config(page_title="Studio Voz Master", page_icon="🎚️", layout="wide")

# --- 0. INICIALIZACIÓN DE ESTADO ---
if 'clean_start' not in st.session_state:
    st.session_state.historial = []
    st.session_state.texto_traducido = ""
    st.session_state.audio_origen = None
    st.session_state.audio_destino = None
    st.session_state.nombres_archivos = {"org": "", "dest": ""}
    st.session_state.rate_val = 0
    st.session_state.pitch_val = 0
    st.session_state.clean_start = True

# --- 1. CABECERA Y DISEÑO (Alineación Perfecta) ---

# CSS LÓGICA
css_base = """
<style>
/* Espacio superior para que no se corte el título */
.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
div[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
textarea { font-size: 1.1rem !important; }
</style>
"""

css_oled = """
<style>
.stApp { background-color: #000000; color: #E0E0E0; }
div[data-testid="stTextArea"] textarea { background-color: #111111; color: #FFFFFF; border: 1px solid #333333; }
div[data-testid="stSelectbox"] > div > div { background-color: #111111; color: white; }
div[data-testid="stSlider"] > div { color: #E0E0E0; }
div[data-testid="stMarkdownContainer"] p { color: #E0E0E0; }
h1, h2, h3 { color: #FFFFFF !important; }
</style>
"""

css_claro = """<style>.stApp { background-color: #FFFFFF; color: #000000; }</style>"""

# Layout de Cabecera
c_tit, c_sel = st.columns([6, 2], gap="medium")

with c_tit:
    # Título
    st.markdown("<h1>🎚️ Studio Voz Master</h1>", unsafe_allow_html=True)

with c_sel:
    # AQUÍ ESTÁ EL AJUSTE: Un espaciador invisible para bajar el selector
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    tema_sel = st.selectbox("Tema", ["OLED (Negro)", "Claro", "Sistema"], label_visibility="collapsed")

# Inyección de CSS según selección
if "Negro" in tema_sel:
    st.markdown(css_base + css_oled, unsafe_allow_html=True)
elif "Claro" in tema_sel:
    st.markdown(css_base + css_claro, unsafe_allow_html=True)
else:
    st.markdown(css_base, unsafe_allow_html=True)


# --- 2. DEFINICIÓN DE VOCES ---
VOCES_LATINAS = {
    "🇨🇴 CO - Salomé": "es-CO-SalomeNeural",
    "🇨🇴 CO - Gonzalo": "es-CO-GonzaloNeural",
    "🇲🇽 MX - Dalia": "es-MX-DaliaNeural",
    "🇲🇽 MX - Jorge": "es-MX-JorgeNeural",
    "🇦🇷 AR - Elena": "es-AR-ElenaNeural",
    "🇦🇷 AR - Tomas": "es-AR-TomasNeural",
    "🇪🇸 ES - Alvaro": "es-ES-AlvaroNeural",
    "🇪🇸 ES - Elvira": "es-ES-ElviraNeural",
    "🇺🇸 US - Paloma": "es-US-PalomaNeural",
    "🇺🇸 US - Alonso": "es-US-AlonsoNeural",
    "🇻🇪 VE - Paola": "es-VE-PaolaNeural",
    "🇵🇪 PE - Camila": "es-PE-CamilaNeural",
    "🇨🇱 CL - Catalina": "es-CL-CatalinaNeural"
}

VOCES_EXTRANJERAS = {
    "🇺🇸 EN - USA (Jenny)":  {"voz": "en-US-JennyNeural", "lang": "en"},
    "🇺🇸 EN - USA (Guy)":    {"voz": "en-US-GuyNeural",   "lang": "en"},
    "🇬🇧 EN - UK (Ryan)":    {"voz": "en-GB-RyanNeural",  "lang": "en"},
    "🇫🇷 FR - France (Denise)": {"voz": "fr-FR-DeniseNeural", "lang": "fr"},
    "🇫🇷 FR - France (Henri)":  {"voz": "fr-FR-HenriNeural",  "lang": "fr"},
    "🇧🇷 PT - Brasil (Francisca)": {"voz": "pt-BR-FranciscaNeural", "lang": "pt"},
    "🇵🇹 PT - Portugal (Raquel)":  {"voz": "pt-PT-RaquelNeural",    "lang": "pt"},
    "🇮🇹 IT - Italia (Isabella)": {"voz": "it-IT-IsabellaNeural", "lang": "it"},
    "🇮🇹 IT - Italia (Diego)":    {"voz": "it-IT-DiegoNeural",    "lang": "it"},
    "🇷🇴 RO - Rumano (Alina)": {"voz": "ro-RO-AlinaNeural", "lang": "ro"},
    "🇩🇪 DE - Alemán (Katja)": {"voz": "de-DE-KatjaNeural", "lang": "de"}
}

VOCES_ORIGEN = VOCES_LATINAS
VOCES_DESTINO = VOCES_EXTRANJERAS.copy()
for nombre, codigo in VOCES_LATINAS.items():
    nombre_limpio = nombre.replace("🇨🇴", "").replace("🇲🇽", "").replace("🇦🇷", "").replace("🇪🇸", "").replace("🇺🇸", "").strip()
    key_name = f"🇪🇸 ES - {nombre_limpio}"
    VOCES_DESTINO[key_name] = {"voz": codigo, "lang": "es"}

# --- 3. FUNCIONES LÓGICAS ---
def generar_nombre_archivo(nombre_voz_full, velocidad, tono):
    nombre_clean = re.sub(r'[^\w\s-]', '', nombre_voz_full).strip()
    nombre_clean = nombre_clean.replace(" ", "_").replace("-", "")
    ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{nombre_clean}_Vel{velocidad}_P{tono}_{ahora}.mp3"

async def generar_audio_engine(texto, voz, velocidad, tono):
    try:
        rate_str = f"{'+' if velocidad >= 0 else ''}{velocidad}%"
        pitch_str = f"{'+' if tono >= 0 else ''}{tono}Hz"
        comunicacion = edge_tts.Communicate(text=texto, voice=voz, rate=rate_str, pitch=pitch_str)
        mp3_fp = io.BytesIO()
        async for chunk in comunicacion.stream():
            if chunk["type"] == "audio":
                mp3_fp.write(chunk["data"])
        return mp3_fp.getvalue()
    except Exception:
        return None

def reset_rate(): st.session_state.rate_val = 0
def reset_pitch(): st.session_state.pitch_val = 0

# --- 4. INTERFAZ ---

col_izq, col_der = st.columns(2, gap="small")

with col_izq:
    st.markdown("### 1. Panel Izquierdo")
    voz_org_nombre = st.selectbox("Voz 1", list(VOCES_ORIGEN.keys()), label_visibility="collapsed")
    voz_org_code = VOCES_ORIGEN[voz_org_nombre]
    
    texto_usuario = st.text_area("Fuente:", height=300, placeholder="Escribe aquí...", key="txt_in")

with col_der:
    st.markdown("### 2. Panel Derecho")
    voz_dest_nombre = st.selectbox("Voz 2", list(VOCES_DESTINO.keys()), label_visibility="collapsed")
    info_dest = VOCES_DESTINO[voz_dest_nombre]
    
    st.text_area("Resultado:", value=st.session_state.texto_traducido, height=300)

# CONTROLES
c_ajustes, c_boton = st.columns([2, 1], gap="medium")

with c_ajustes:
    st.markdown("### Ajustes")
    k1, k2 = st.columns(2)
    with k1:
        s1, b1 = st.columns([5,1])
        velocidad = s1.slider("Velocidad (%)", -100, 100, key="rate_val", step=1)
        b1.button("↺", key="rv", on_click=reset_rate)
    with k2:
        s2, b2 = st.columns([5,1])
        tono = s2.slider("Tono (Hz)", -50, 50, key="pitch_val", step=1)
        b2.button("↺", key="rp", on_click=reset_pitch)

with c_boton:
    st.write("") 
    st.write("")
    if st.button("⚡ PROCESAR", type="primary", use_container_width=True):
        if not texto_usuario.strip():
            st.warning("El texto está vacío.")
        else:
            with st.spinner('Procesando...'):
                try:
                    # Traducción
                    if info_dest['lang'] == 'es':
                        resultado_traduccion = texto_usuario
                    else:
                        translator = GoogleTranslator(source='auto', target=info_dest['lang'])
                        resultado_traduccion = translator.translate(texto_usuario)

                    st.session_state.texto_traducido = resultado_traduccion

                    # Audio
                    audio_es = asyncio.run(generar_audio_engine(texto_usuario, voz_org_code, velocidad, tono))
                    audio_tr = asyncio.run(generar_audio_engine(resultado_traduccion, info_dest['voz'], velocidad, tono))

                    if audio_es and audio_tr:
                        fn_org = generar_nombre_archivo(voz_org_nombre, velocidad, tono)
                        fn_dest = generar_nombre_archivo(voz_dest_nombre, velocidad, tono)

                        st.session_state.audio_origen = audio_es
                        st.session_state.audio_destino = audio_tr
                        st.session_state.nombres_archivos = {"org": fn_org, "dest": fn_dest}
                        
                        now = datetime.now().strftime("%H:%M:%S")
                        st.session_state.historial.insert(0, {
                            "hora": now,
                            "org_txt": texto_usuario,
                            "dest_txt": resultado_traduccion,
                            "org_aud": audio_es,
                            "dest_aud": audio_tr,
                            "org_name": fn_org,
                            "dest_name": fn_dest
                        })
                        st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")

# RESULTADOS
if st.session_state.audio_origen and st.session_state.audio_destino:
    st.divider()
    r1, r2 = st.columns(2, gap="medium")
    with r1:
        st.audio(st.session_state.audio_origen, format='audio/mp3')
        st.download_button(f"⬇️ {st.session_state.nombres_archivos['org']}", st.session_state.audio_origen, file_name=st.session_state.nombres_archivos['org'], mime="audio/mp3", type="secondary", use_container_width=True)
    with r2:
        st.audio(st.session_state.audio_destino, format='audio/mp3')
        st.download_button(f"⬇️ {st.session_state.nombres_archivos['dest']}", st.session_state.audio_destino, file_name=st.session_state.nombres_archivos['dest'], mime="audio/mp3", type="secondary", use_container_width=True)

# HISTORIAL
if st.session_state.historial:
    st.markdown("---")
    st.markdown("### 📂 Biblioteca")
    for i, item in enumerate(st.session_state.historial):
        with st.expander(f"{item['hora']} | {item['org_name']} | {item['dest_name']}"):
            h1, h2 = st.columns(2)
            with h1:
                st.caption(item['org_txt'])
                st.download_button("⬇️ Descargar Izq", item['org_aud'], file_name=item['org_name'], key=f"ho_{i}")
            with h2:
                st.caption(item['dest_txt'])
                st.download_button("⬇️ Descargar Der", item['dest_aud'], file_name=item['dest_name'], key=f"hd_{i}")