import streamlit as st

# Configuração da página (opcional, mas recomendado)
st.set_page_config(
    page_title="Análise de Ativos",
    page_icon="📊",
    layout="wide"
)

# Título Principal da Aplicação
st.title("Plataforma de Análise de Bonds e Equity")

# Mensagem de boas-vindas
st.markdown("""
Bem-vindo à nossa plataforma de análise de investimentos!

Esta é a **primeira versão** da nossa ferramenta, construída de forma incremental
com foco em simplicidade e eficiência.

**Nosso objetivo:** Transformar dados em decisões de investimento mais inteligentes.
""")

# Uma pequena celebração :)
st.balloons()
