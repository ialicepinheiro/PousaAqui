# ✈️ PousaAqui - Painel de Monitoramento de Passagens Aéreas

O **PousaAqui** é um aplicativo interativo construído em Python com **Streamlit** que permite buscar, comparar e monitorar o histórico de preços de passagens aéreas usando a API do **Google Flights** (via SerpApi).

---

## 🚀 Funcionalidades

- 🔍 **Busca Dinâmica com Autocomplete:** Digite o nome de qualquer cidade ou aeroporto do mundo e receba sugestões automáticas.
- ✈️ **Consulta ao Google Flights:** Obtém o menor preço, duração total, número de escalas e horário de saída/chegada do voo.
- 🗓️ **Flexibilidade de Datas:** Suporte para pesquisas de Somente Ida ou Ida e Volta.
- 📊 **Gráfico de Histórico de Preços:** Salve buscas de preços para visualizar a evolução dos valores ao longo do tempo em gráficos de linha.
- 💾 **Armazenamento Local:** Registra as buscas monitoradas em um arquivo CSV (`historico_precos.csv`).

---

## 🛠️ Tecnologias Utilizadas

- **[Python](https://www.python.org/)** - Linguagem principal do projeto.
- **[Streamlit](https://streamlit.io/)** - Interface web interativa.
- **[SerpApi](https://serpapi.com/)** - API para coleta de dados do Google Flights.
- **[Pandas](https://pandas.pydata.org/)** & **[Matplotlib](https://matplotlib.org/)** - Manipulação de dados e geração do gráfico de histórico.
- **[streamlit-searchbox](https://github.com/m-c-k-l/streamlit-searchbox)** - Componente de busca com autocomplete em tempo real.

---

## 📋 Pré-requisitos

Antes de começar, você precisará ter instalado em sua máquina:
- Python 3.9 ou superior.
- Uma chave de API gratuita da **[SerpApi](https://serpapi.com/)**.

---

## 🔧 Passo a Passo de Instalação

### 1. Clone o repositório
```bash
git clone [https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git](https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git)
cd NOME_DO_REPOSITORIO