# ✈️ PousaAqui - Painel de Monitoramento de Passagens Aéreas

O **PousaAqui** é uma aplicação web interativa desenvolvida com **Streamlit** para busca, monitoramento e análise de preços de voos. Ela consome dados em tempo real através da **SerpApi (Google Flights & Google Travel Explore)** e permite salvar o histórico das buscas em um banco de dados para analisar a variação e tendência de tarifas ao longo do tempo.

---

## ✨ Funcionalidades

- **🔍 Busca Inteligente & Autocomplete:**
  - Digite qualquer nome de cidade ou código IATA de aeroporto com sugestões em tempo real (`google_flights_autocomplete`).
  - Suporte a voos de ida e de ida e volta.
- **⚡ Busca Multi-Fonte:**
  - Consulta detalhada no **Google Flights** com identificação automática do voo mais barato e mais rápido.
  - Varredura em ofertas promocionais (**Google Flights Deals**) e destinos (**Google Travel Explore**).
- **📈 Gráficos e Análise Histórica:**
  - Visualização gráfica da evolução dos preços das passagens pesquisadas usando **Plotly**.
  - Indicadores de tendência (Preço Atual, Menor Preço Histórico e Maior Preço Histórico).
- **💾 Gerenciamento de Histórico (CRUD):**
  - Armazenamento dos voos salvos em banco de dados SQLite.
  - Exclusão individual de registros salvos ou reset completo da base de dados.
  - Exportação dos dados coletados em formato **CSV**.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.9+
- **Interface Web:** [Streamlit](https://streamlit.io/)
- **Visualização de Dados:** [Plotly Express](https://plotly.com/python/) & Pandas
- **APIs de Voos:** [SerpApi](https://serpapi.com/) (Google Flights Engine)
- **Banco de Dados:** SQLite3
- **Controle de Variáveis de Ambiente:** `python-dotenv`

---