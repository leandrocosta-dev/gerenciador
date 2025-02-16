import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
# from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Controle de Veículos", layout="wide")

# Configuração da conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Funções para manipulação de dados
def load_data(worksheet):
    try:
        data = conn.read(worksheet=worksheet, ttl=5)
        if data.empty:
            return pd.DataFrame()  # Retorna um DataFrame vazio
        
        # Ensure 'Km_Atual' exists for 'Veiculos' worksheet
        if worksheet == 'Veiculos' and 'Km_Atual' not in data.columns:
            data['Km_Atual'] = data['Km_Inicial']
            
        return data
    except Exception:
        return pd.DataFrame()

def save_data(data, worksheet):
    conn.update(worksheet=worksheet, data=data)

# Função para calcular consumo médio
def calcular_consumo_medio(df, veiculo):
    veiculo_df = df[df['Veículo'] == veiculo].copy()
    if len(veiculo_df) <= 1:
        return 0.0
    
    # Ordenar por data
    veiculo_df = veiculo_df.sort_values('Data')
    
    # Converter km para numérico
    veiculo_df['Km_Atual'] = pd.to_numeric(veiculo_df['Km_Atual'], errors='coerce')
    
    # Calcular diferenças
    veiculo_df['km_diff'] = veiculo_df['Km_Atual'].diff()
    veiculo_df['litros_ant'] = veiculo_df['Litros'].shift(1)
    
    # Remover primeira linha (não tem diferença) e linhas com NaN
    veiculo_df = veiculo_df.dropna(subset=['km_diff', 'litros_ant'])
    
    if len(veiculo_df) == 0:
        return 0.0
    
    # Calcular consumo por abastecimento
    veiculo_df['consumo'] = veiculo_df['km_diff'] / veiculo_df['litros_ant']
    
    # Retornar média dos consumos
    return veiculo_df['consumo'].mean()

# Função para calcular consumo ao longo do tempo
def calcular_consumo_por_abastecimento(df):
    # Fazemos uma cópia para preservar o dataframe original
    result_df = df.copy()
    
    # Converter km para numérico se já não for
    result_df['Km_Atual'] = pd.to_numeric(result_df['Km_Atual'], errors='coerce')
    result_df['Litros'] = pd.to_numeric(result_df['Litros'], errors='coerce')
    
    # Inicializar a coluna de consumo com NaN
    result_df['Consumo_km_l'] = float('nan')
    
    # Processar cada veículo separadamente
    for veiculo in result_df['Veículo'].unique():
        # Filtrar dados do veículo
        veiculo_df = result_df[result_df['Veículo'] == veiculo].copy()
        
        # Ordenar por data
        veiculo_df = veiculo_df.sort_values('Data')
        
        # Calcular diferença de quilometragem
        veiculo_df['km_diff'] = veiculo_df['Km_Atual'].diff()
        
        # Deslocar os litros para pegar o abastecimento anterior
        veiculo_df['litros_ant'] = veiculo_df['Litros'].shift(1)
        
        # Calcular o consumo (km/l)
        veiculo_df['Consumo_km_l'] = veiculo_df['km_diff'] / veiculo_df['litros_ant']
        
        # Atualizar o dataframe original
        result_df.loc[veiculo_df.index, 'Consumo_km_l'] = veiculo_df['Consumo_km_l']
    
    # Remover as linhas onde não foi possível calcular o consumo
    result_df = result_df.dropna(subset=['Consumo_km_l'])
    
    return result_df

# Estilo CSS personalizado
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
    }
    .big-metric {
        font-size: 24px;
        font-weight: bold;
        text-align: center;
        padding: 20px;
        background-color: #4CAF50;
        border-radius: 10px;
        margin: 10px 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Menu principal
selected = option_menu(
    menu_title=None,
    options=["Cadastro", "Abastecimento", "Manutenção", "Relatórios"],
    icons=["car-front", "fuel-pump", "tools", "graph-up"],
    orientation="horizontal",
)

# Carregar dados dos veículos
if 'veiculos_df' not in st.session_state:
    try:
        st.session_state.veiculos_df = load_data('Veiculos')
    except:
        st.session_state.veiculos_df = pd.DataFrame(columns=['Nome', 'Marca', 'Km_Inicial', 'Km_Atual', 'Data_Registro'])

if selected == "Cadastro":
    st.header("📝 Cadastro de Veículo")
    
    with st.form("cadastro_veiculo"):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("🚗 Nome do Veículo")
            marca = st.text_input("🏢 Marca do Veículo")
        with col2:
            km_inicial = st.number_input("📏 Km Inicial", min_value=0)
            data_registro = st.date_input("📅 Data de Registro")
        
        submitted = st.form_submit_button("💾 Salvar Dados")
        if submitted:
            # Corrigido para incluir Km_Atual igual a Km_Inicial
            new_data = pd.DataFrame({
                'Nome': [nome],
                'Marca': [marca],
                'Km_Inicial': [km_inicial],
                'Km_Atual': [km_inicial],
                'Data_Registro': [data_registro.strftime('%Y-%m-%d')]
            })
            updated_df = pd.concat([st.session_state.veiculos_df, new_data], ignore_index=True)
            save_data(updated_df, 'Veiculos')
            st.session_state.veiculos_df = updated_df
            st.success("Veículo cadastrado com sucesso!")

elif selected == "Abastecimento":
    st.header("⛽ Registro de Abastecimento")
    
    # Verificar se existem veículos cadastrados
    if len(st.session_state.veiculos_df) == 0:
        st.warning("Não há veículos cadastrados. Por favor, cadastre um veículo primeiro.")
    else:
        with st.form("registro_abastecimento"):
            veiculo = st.selectbox("🚗 Selecione o Veículo", 
                                st.session_state.veiculos_df['Nome'].tolist())
            
            # Encontrar km atual do veículo selecionado
            veiculo_info = st.session_state.veiculos_df[st.session_state.veiculos_df['Nome'] == veiculo]
            km_ultimo = veiculo_info['Km_Atual'].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                data_abast = st.date_input("📅 Data do Abastecimento")
                preco_comb = st.number_input("💰 Preço do Combustível (por litro)", 
                                          min_value=0.0, step=0.01)
                km_atual = st.number_input("🎯 Km Atual", min_value=float(km_ultimo), 
                                        value=float(km_ultimo), step=1.0)
            with col2:
                qtd_litros = st.number_input("🛢️ Quantidade de Litros", 
                                          min_value=0.0, step=0.1)
                # Calcula o valor total automaticamente
                valor_total = preco_comb * qtd_litros
                st.markdown(f"💵 **Valor Total:** R$ {valor_total:.2f}")
                if km_atual > km_ultimo:
                    st.info(f"Distância percorrida desde último registro: {km_atual - km_ultimo:.1f} km")
            
            submitted = st.form_submit_button("💾 Salvar Dados")
            if submitted:
                try:
                    abastecimentos_df = load_data('Abastecimentos')
                except:
                    abastecimentos_df = pd.DataFrame(
                        columns=['Veículo', 'Data', 'Preço', 'Litros', 'Valor', 'Km_Atual'])
                
                new_data = pd.DataFrame({
                    'Veículo': [veiculo],
                    'Data': [data_abast.strftime('%Y-%m-%d')], 
                    'Preço': [preco_comb],
                    'Litros': [qtd_litros],
                    'Valor': [valor_total],
                    'Km_Atual': [km_atual]
                })
                
                updated_df = pd.concat([abastecimentos_df, new_data], ignore_index=True)
                save_data(updated_df, 'Abastecimentos')
                
                # Atualizar Km_Atual do veículo
                veiculo_idx = st.session_state.veiculos_df[st.session_state.veiculos_df['Nome'] == veiculo].index[0]
                st.session_state.veiculos_df.loc[veiculo_idx, 'Km_Atual'] = km_atual
                save_data(st.session_state.veiculos_df, 'Veiculos')
                
                st.success("Abastecimento registrado com sucesso!")

elif selected == "Manutenção":
    st.header("🔧 Registro de Manutenção")
    
    # Verificar se existem veículos cadastrados
    if len(st.session_state.veiculos_df) == 0:
        st.warning("Não há veículos cadastrados. Por favor, cadastre um veículo primeiro.")
    else:
        with st.form("registro_manutencao"):
            veiculo = st.selectbox("🚗 Selecione o Veículo", 
                                st.session_state.veiculos_df['Nome'].tolist())
            
            # Encontrar km atual do veículo selecionado
            veiculo_info = st.session_state.veiculos_df[st.session_state.veiculos_df['Nome'] == veiculo]
            km_ultimo = veiculo_info['Km_Atual'].iloc[0]
            
            col1, col2 = st.columns(2)
            with col1:
                data_manut = st.date_input("📅 Data da Manutenção")
                preco = st.number_input("💰 Preço", min_value=0.0, step=0.01)
                km_atual = st.number_input("🎯 Km Atual", min_value=float(km_ultimo), 
                                        value=float(km_ultimo), step=1.0)
            with col2:
                descricao = st.text_area("📝 Descrição da Manutenção")
                if km_atual > km_ultimo:
                    st.info(f"Distância percorrida desde último registro: {km_atual - km_ultimo:.1f} km")
            
            submitted = st.form_submit_button("💾 Salvar Dados")
            if submitted:
                try:
                    manutencoes_df = load_data('Manutencoes')
                except:
                    manutencoes_df = pd.DataFrame(
                        columns=['Veiculo', 'Data', 'Valor', 'Descricao', 'Km_Atual'])
                
                new_data = pd.DataFrame({
                    'Veiculo': [veiculo],
                    'Data': [data_manut.strftime('%Y-%m-%d')],
                    'Valor': [preco],
                    'Descricao': [descricao],
                    'Km_Atual': [km_atual]
                })
                
                updated_df = pd.concat([manutencoes_df, new_data], ignore_index=True)
                save_data(updated_df, 'Manutencoes')
                
                # Atualizar Km_Atual do veículo
                veiculo_idx = st.session_state.veiculos_df[st.session_state.veiculos_df['Nome'] == veiculo].index[0]
                st.session_state.veiculos_df.loc[veiculo_idx, 'Km_Atual'] = km_atual
                save_data(st.session_state.veiculos_df, 'Veiculos')
                
                st.success("Manutenção registrada com sucesso!")

else:  # Relatórios
    st.header("📊 Relatórios")
    
    # Carregar dados para relatórios
    try:
        abast_df = load_data('Abastecimentos')
        manut_df = load_data('Manutencoes')
        
        # Verificar se temos dados suficientes
        if abast_df.empty and manut_df.empty:
            st.warning("Não há dados suficientes para gerar relatórios. Por favor, registre abastecimentos e manutenções.")
            st.stop()
            
    except:
        st.error("Erro ao carregar dados dos relatórios")
        st.stop()
    
    # Converter colunas numéricas e datas
    if not abast_df.empty:
        abast_df['Litros'] = pd.to_numeric(abast_df['Litros'], errors='coerce')
        abast_df['Valor'] = pd.to_numeric(abast_df['Valor'], errors='coerce')
        abast_df['Km_Atual'] = pd.to_numeric(abast_df['Km_Atual'], errors='coerce')
        abast_df['Data'] = pd.to_datetime(abast_df['Data'])
    
    if not manut_df.empty:
        manut_df['Valor'] = pd.to_numeric(manut_df['Valor'], errors='coerce')
        manut_df['Km_Atual'] = pd.to_numeric(manut_df['Km_Atual'], errors='coerce')
        manut_df['Data'] = pd.to_datetime(manut_df['Data'])
    
    # Seletor de período
    periodo_opcoes = {
        "Todo o período": None,
        "Mês atual": pd.Timestamp.now().strftime("%Y-%m"),
        "Últimos 3 meses": (pd.Timestamp.now() - pd.DateOffset(months=3)).strftime("%Y-%m"),
        "Últimos 6 meses": (pd.Timestamp.now() - pd.DateOffset(months=6)).strftime("%Y-%m"),
        "Este ano": pd.Timestamp.now().strftime("%Y")
    }
    
    periodo = st.selectbox("📅 Selecione o período", options=list(periodo_opcoes.keys()))
    
    # Filtrar dados com base no período selecionado
    if not abast_df.empty and periodo != "Todo o período":
        if "mês" in periodo.lower():
            abast_df = abast_df[abast_df['Data'].dt.strftime("%Y-%m") >= periodo_opcoes[periodo]]
        elif "ano" in periodo.lower():
            abast_df = abast_df[abast_df['Data'].dt.strftime("%Y") >= periodo_opcoes[periodo]]
    
    if not manut_df.empty and periodo != "Todo o período":
        if "mês" in periodo.lower():
            manut_df = manut_df[manut_df['Data'].dt.strftime("%Y-%m") >= periodo_opcoes[periodo]]
        elif "ano" in periodo.lower():
            manut_df = manut_df[manut_df['Data'].dt.strftime("%Y") >= periodo_opcoes[periodo]]
    
    # Calcular consumo por abastecimento (para o gráfico de consumo)
    if not abast_df.empty:
        abast_consumo_df = calcular_consumo_por_abastecimento(abast_df)
    
    # Criar cards de métricas em duas linhas
    st.markdown("### 📊 Métricas Gerais")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_litros = 0 if abast_df.empty else abast_df['Litros'].sum()
        st.markdown(f"""
            <div class="big-metric">
                CONSUMO TOTAL DE LITROS<br>
                {total_litros:.2f} L
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        total_gasto_comb = 0 if abast_df.empty else abast_df['Valor'].sum()
        st.markdown(f"""
            <div class="big-metric">
                GASTO TOTAL COM COMBUSTÍVEL<br>
                R$ {total_gasto_comb:.2f}
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        total_gasto_manut = 0 if manut_df.empty else manut_df['Valor'].sum()
        st.markdown(f"""
            <div class="big-metric">
                GASTO TOTAL COM MANUTENÇÃO<br>
                R$ {total_gasto_manut:.2f}
            </div>
        """, unsafe_allow_html=True)

    # Nova linha para consumo médio
    if not abast_df.empty:
        st.markdown("### 🚗 Consumo Médio por Veículo")
        
        # Obter lista de veículos
        veiculos = abast_df['Veículo'].unique()
        
        # Criar colunas dinamicamente baseado no número de veículos
        cols = st.columns(len(veiculos))
        
        # Calcular e mostrar consumo médio para cada veículo
        for idx, veiculo in enumerate(veiculos):
            consumo_medio = calcular_consumo_medio(abast_df, veiculo)
            with cols[idx]:
                st.markdown(f"""
                    <div class="big-metric">
                        {veiculo}<br>
                        {consumo_medio:.2f} km/L
                    </div>
                """, unsafe_allow_html=True)
    
    # Gráficos
    st.markdown("### 📈 Gráficos")
    
    # Verifica se temos dados para gráficos
    if abast_df.empty and manut_df.empty:
        st.info("Não há dados suficientes para gerar gráficos.")
    else:
        # NOVO GRÁFICO DE CONSUMO KM/L AO LONGO DO TEMPO
        if not abast_df.empty and len(abast_consumo_df) > 0:
            st.subheader("📊 Consumo (km/L) ao Longo do Tempo por Veículo")
            
            # Formatar data para exibição
            abast_consumo_df['Data_formatada'] = abast_consumo_df['Data'].dt.strftime('%d/%m/%Y')
            
            # Criar o gráfico de barras de consumo
            fig_consumo = px.bar(
                abast_consumo_df,
                x='Data_formatada',
                y='Consumo_km_l',
                color='Veículo',
                barmode='group',
                title='CONSUMO (KM/L) AO LONGO DO TEMPO',
                hover_data={
                    'Data_formatada': True,
                    'Veículo': True,
                    'Consumo_km_l': ':.2f',
                    'Km_Atual': True,
                    'Litros': True
                },
                height=500
            )
            
            fig_consumo.update_layout(
                xaxis_title="Data do Abastecimento",
                yaxis_title="Consumo (km/L)",
                legend_title="Veículo",
                xaxis={'categoryorder': 'category ascending'},
                hovermode='closest',
                xaxis_tickangle=-45
            )
            
            # Adicionar linha com o consumo médio de cada veículo
            for veiculo in abast_df['Veículo'].unique():
                consumo_medio = calcular_consumo_medio(abast_df, veiculo)
                if consumo_medio > 0:
                    fig_consumo.add_shape(
                        type="line",
                        x0=0,
                        y0=consumo_medio,
                        x1=1,
                        y1=consumo_medio,
                        xref="paper",
                        line=dict(color="rgba(0,0,0,0.5)", dash="dash"),
                    )
                    fig_consumo.add_annotation(
                        x=0.02,
                        y=consumo_medio,
                        xref="paper",
                        text=f"Média {veiculo}: {consumo_medio:.1f} km/L",
                        showarrow=False,
                        bgcolor="rgba(0, 4, 255, 0.8)",
                        font=dict(size=10)
                    )
            
            st.plotly_chart(fig_consumo, use_container_width=True)
        
        # Outros gráficos em duas colunas
        col1, col2 = st.columns(2)
        
        # Gráficos de Abastecimento
        if not abast_df.empty:
            with col1:
                # Agrupar os dados de abastecimento por data e veículo
                abast_mensal = abast_df.copy()
                abast_mensal['Dia'] = abast_mensal['Data'].dt.strftime('%Y-%m-%d')
                abast_mensal = abast_mensal.groupby(['Dia', 'Veículo'])['Litros'].sum().reset_index()

                # Criar o gráfico de linhas
                fig_comb = px.line(abast_mensal,
                                x='Dia',
                                y='Litros',
                                color='Veículo',
                                title='DATAS DE ABASTECIMENTO POR VEÍCULO',
                                markers=True)

                fig_comb.update_layout(
                    xaxis_title="Dia",
                    yaxis_title="Litros",
                    hovermode='x unified'
                )

                st.plotly_chart(fig_comb, use_container_width=True)
            
            with col2:
                # Gráfico de barras - Consumo de litros por veículo
                fig_litros = px.bar(abast_df.groupby('Veículo')['Litros']
                                .sum().reset_index(),
                                x='Veículo',
                                y='Litros',
                                title='CONSUMO TOTAL DE LITROS POR VEÍCULO')
                fig_litros.update_layout(
                    xaxis_title="Veículo",
                    yaxis_title="Litros"
                )
                st.plotly_chart(fig_litros, use_container_width=True)
                
        # Gráficos de Manutenção
        if not manut_df.empty:
            with col1:
                # Gráfico de pizza - Gastos com manutenção por veículo
                fig_manut_pizza = px.pie(manut_df.groupby('Veiculo')['Valor']
                                        .sum().reset_index(),
                                        values='Valor',
                                        names='Veiculo',
                                        title='GASTO COM MANUTENÇÃO POR VEÍCULO')
                st.plotly_chart(fig_manut_pizza, use_container_width=True)
            
            with col2:
                # Gráfico de linha - Gastos com manutenção por veículo
                manut_mensal = manut_df.copy()
                manut_mensal['Mês'] = manut_mensal['Data'].dt.strftime('%Y-%m')
                manut_mensal = manut_mensal.groupby(['Mês', 'Veiculo'])['Valor'].sum().reset_index()
                
                fig_manut = px.line(manut_mensal,
                                x='Mês',
                                y='Valor',
                                color='Veiculo',
                                title='GASTO COM MANUTENÇÃO POR VEÍCULO',
                                markers=True)
                
                fig_manut.update_layout(
                    xaxis_title="Mês",
                    yaxis_title="Valor (R$)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig_manut, use_container_width=True)
