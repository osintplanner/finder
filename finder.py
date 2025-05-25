import os
import psycopg2
from flask import Flask, render_template, request, flash, redirect, url_for
from datetime import datetime # Para o rodapé

# Cria a instância da aplicação Flask
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "defina_uma_chave_secreta_forte_em_producao_finder")

# --- Funções do Banco de Dados (APENAS CONSULTA E CONTAGEM) ---

def obter_conexao_db():
    """Obtém uma conexão com o banco de dados PostgreSQL."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERRO FATAL: Variável de ambiente DATABASE_URL não configurada.")
        raise ConnectionError("DATABASE_URL não configurada.")
    # Render geralmente requer sslmode=require para conexões seguras
    conn = psycopg2.connect(db_url, sslmode=os.environ.get('DB_SSLMODE', 'prefer'))
    return conn

def verificar_endereco_no_db(endereco_pesquisado):
    """Verifica um endereço no banco de dados PostgreSQL."""
    conn = None
    try:
        conn = obter_conexao_db()
        with conn.cursor() as cur:
            cur.execute("SELECT servico_nome FROM enderecos_servicos WHERE endereco = %s;", (endereco_pesquisado.strip(),))
            resultado_db = cur.fetchone()
        
        if resultado_db:
            return True, resultado_db[0] # resultado_db[0] é o nome do serviço
        else:
            return False, None
    except psycopg2.Error as e:
        print(f"ERRO de Banco de Dados ao consultar endereço '{endereco_pesquisado}': {e}")
        return False, f"Erro de comunicação com o banco de dados ({e.pgcode if hasattr(e, 'pgcode') else 'N/A'})."
    except Exception as e:
        print(f"ERRO geral ao consultar o banco de dados para '{endereco_pesquisado}': {e}")
        return False, "Erro interno ao consultar o banco de dados."
    finally:
        if conn:
            conn.close()

def contar_enderecos_no_db():
    """Conta o número total de endereços na base de dados."""
    conn = None
    try:
        conn = obter_conexao_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM enderecos_servicos;")
            total = cur.fetchone()[0]
        return total
    except Exception as e:
        print(f"ERRO ao contar endereços no banco de dados: {e}")
        return "N/A (erro)" # Retorna uma string indicando erro na contagem
    finally:
        if conn:
            conn.close()

# --- Rotas da Aplicação Flask ---
@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_busca = None
    endereco_pesquisado_form = ""
    if request.method == 'POST':
        endereco_pesquisado_form = request.form.get('endereco', '').strip()
        if endereco_pesquisado_form:
            encontrado, info_servico = verificar_endereco_no_db(endereco_pesquisado_form)
            if encontrado:
                resultado_busca = {"status": "encontrado", "endereco": endereco_pesquisado_form, "servico": info_servico}
            else:
                msg_erro = info_servico if isinstance(info_servico, str) else "O endereço não consta na lista de serviços conhecidos."
                resultado_busca = {"status": "nao_encontrado", "endereco": endereco_pesquisado_form, "servico_msg": msg_erro}
        else:
            flash("Por favor, insira um endereço para pesquisar.", "warning")
            
    num_enderecos_base = contar_enderecos_no_db()
    # Para o rodapé do HTML
    now = datetime.now()
    return render_template('index.html', 
                           resultado=resultado_busca, 
                           endereco_pesquisado=endereco_pesquisado_form, 
                           num_enderecos=num_enderecos_base,
                           now=now)

@app.route('/admin/data_update_info') # Rota informativa
def data_update_info_route():
    flash("A base de dados é atualizada periodicamente por um processo administrativo separado. Contate o administrador para informações sobre a última atualização ou para solicitar uma nova.", "info")
    return redirect(url_for('index'))

# --- Inicialização ---
if __name__ == '__main__':
    print("INFO: Iniciando aplicação Flask (Modo Banco de Dados - Consulta)...")
    
    # Verifica a conexão com o banco de dados na inicialização (opcional, mas bom para feedback rápido)
    try:
        conn_teste = obter_conexao_db()
        print("INFO: Tentando verificar conexão com o banco de dados...")
        with conn_teste.cursor() as cur_teste:
             cur_teste.execute("SELECT 1;") # Query simples para testar a conexão
             if cur_teste.fetchone():
                print("INFO: Conexão com o banco de dados estabelecida com sucesso.")
             # Verifica se a tabela principal existe (criada pelo script de ingestão)
             cur_teste.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'enderecos_servicos');")
             if not cur_teste.fetchone()[0]:
                 print("AVISO IMPORTANTE: Tabela 'enderecos_servicos' não encontrada no banco de dados.")
                 print("                 Execute o script 'ingest_data.py' para criar a tabela e popular os dados.")
        conn_teste.close()
    except Exception as e:
        print(f"ERRO CRÍTICO: Não foi possível conectar ao banco de dados na inicialização: {e}")
        print("      Verifique sua variável de ambiente DATABASE_URL e as configurações do banco de Dados.")
        print("      A aplicação pode não funcionar corretamente até que o banco de dados esteja acessível e populado.")

    # Porta para o Render (Render define a variável PORT)
    port = int(os.environ.get("PORT", 5000))
    # debug=False para produção. Para Render, Gunicorn será usado via Procfile.
    app.run(debug=False, host='0.0.0.0', port=port)