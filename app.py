from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import pyodbc
import pandas as pd
import re
from datetime import datetime, timedelta
import threading
import time
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'  # Necessário para Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

def get_warehouse_data(device_code):
    # Configurações de conexão
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    
    try:
        # Estabelece a conexão
        conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        )
 
        # Primeira consulta SQL (SheinBox)
        query1 = f"""
        SELECT DestinationWarehouseCode,
               DestinationWarehouseArea,
               ShelfContainerNumber,
               DeviceCode,
               ActualArrivalDestination,
               NumberOfSubPackages,
               DATEDIFF(SECOND, CreationTime, GETDATE()) AS TimeDifference_Seconds,
               CAST(DATEADD(SECOND, DATEDIFF(SECOND, CreationTime, GETDATE()), '00:00:00') AS TIME) AS TimeDifference,
               TransferStatus
        FROM SheinBox
        WHERE CAST(CreationTime AS DATE) BETWEEN CAST(GETDATE() - 1 AS DATE) AND CAST(GETDATE() AS DATE)
        AND ShipmentTime IS NULL
        AND TransferStatus = 'RC Loading'
        AND DeviceCode LIKE '%{device_code}%'
        ORDER BY ActualArrivalDestination
        """
 
        # Segunda consulta SQL (SheinLabelOutbound)
        query2 = f"""
        SELECT DeviceCode,
               ShipmentContainerNumber,
               ActualArrivalDestination,
               NumberOfPackages,
               Status,
               DATEDIFF(SECOND, BoxingStartTime, GETDATE()) AS TimeDifference_Seconds,
               CAST(DATEADD(SECOND, DATEDIFF(SECOND, BoxingStartTime, GETDATE()), '00:00:00') AS TIME) AS TimeDifference,
               CAST(SUBSTRING(ActualArrivalDestination, CHARINDEX('-', ActualArrivalDestination) + 1, LEN(ActualArrivalDestination)) AS INT) AS TextAfterDelimiter,
               BoxingStartTime AS CreationTime
        FROM SheinLabelOutbound
        WHERE CAST(BoxingStartTime AS DATE) BETWEEN CAST(GETDATE() - 1 AS DATE) AND CAST(GETDATE() AS DATE)
        AND ShipmentTime IS NULL
        AND BoxingStartTime is NOT NULL
        AND DeviceCode LIKE '%{device_code}%'
        AND Status = 'In the process of boxing'
        """
 
        # Lê os dados em DataFrames
        df1 = pd.read_sql(query1, conn)
        df2 = pd.read_sql(query2, conn)
 
        # Verifica se há dados em ambos os DataFrames
        if df1.empty and df2.empty:
            return {
                'status': 'no_data',
                'message': 'Nenhum dado encontrado para este sorter no momento.',
                'sheinbox': [],
                'outbound': []
            }
 
        # Converte os DataFrames para listas de dicionários
        data_sheinbox = df1.to_dict(orient='records')
        data_outbound = df2.to_dict(orient='records')
 
        return {
            'status': 'success',
            'sheinbox': data_sheinbox,
            'outbound': data_outbound
        }
 
    except pyodbc.Error as e:
        return {
            'status': 'db_error',
            'message': f"Erro na conexão com o banco de dados: {str(e)}",
            'sheinbox': [],
            'outbound': []
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f"Erro inesperado: {str(e)}",
            'sheinbox': [],
            'outbound': []
        }
    finally:
        if 'conn' in locals():
            conn.close()

def get_overtime_data():
    # Configurações de conexão
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
 
    try:
        # Estabelece a conexão
        conn = pyodbc.connect(
            f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'
        )
 
        # [Suas queries SQL permanecem as mesmas]
        query1 = """
        SELECT 
            DeviceCode,
            DestinationWarehouseCode,
            DestinationWarehouseArea,
            ShelfContainerNumber,
            ActualArrivalDestination,
            NumberOfSubPackages,
            CreationTime,
            DATEDIFF(SECOND, CreationTime, GETDATE()) AS TimeDifference_Seconds,
            CAST(DATEADD(SECOND, DATEDIFF(SECOND, CreationTime, GETDATE()), '00:00:00') AS TIME) AS TimeDifference,
            TransferStatus
        FROM SheinBox
        WHERE CAST(CreationTime AS DATE) BETWEEN CAST(GETDATE() - 1 AS DATE) AND CAST(GETDATE() AS DATE)
            AND ShipmentTime IS NULL
            AND TransferStatus = 'RC Loading'
            AND DATEDIFF(MINUTE, CreationTime, GETDATE()) > 120
        ORDER BY TimeDifference_Seconds DESC, DeviceCode
        """
 
        query2 = """
        SELECT 
            DeviceCode,
            ShipmentContainerNumber,
            ActualArrivalDestination,
            NumberOfPackages,
            Status,
            BoxingStartTime AS CreationTime,
            DATEDIFF(SECOND, BoxingStartTime, GETDATE()) AS TimeDifference_Seconds,
            CAST(DATEADD(SECOND, DATEDIFF(SECOND, BoxingStartTime, GETDATE()), '00:00:00') AS TIME) AS TimeDifference
        FROM SheinLabelOutbound
        WHERE CAST(BoxingStartTime AS DATE) BETWEEN CAST(GETDATE() - 1 AS DATE) AND CAST(GETDATE() AS DATE)
            AND ShipmentTime IS NULL
            AND BoxingStartTime is NOT NULL
            AND Status = 'In the process of boxing'
            AND DATEDIFF(MINUTE, BoxingStartTime, GETDATE()) > 120
        ORDER BY TimeDifference_Seconds DESC, DeviceCode
        """
 
        # Lê os dados em DataFrames
        df1 = pd.read_sql(query1, conn)
        df2 = pd.read_sql(query2, conn)
 
        # Agrupa os dados por DeviceCode para estatísticas (modificado para evitar multi-índice)
        stats_sheinbox = df1.groupby('DeviceCode').agg({
            'ShelfContainerNumber': 'count',
            'TimeDifference_Seconds': ['mean', 'max', 'min']
        }).round(2)
        
        # Renomeia as colunas para nomes simples
        stats_sheinbox.columns = [
            'count',
            'mean_seconds',
            'max_seconds',
            'min_seconds'
        ]
        stats_sheinbox = stats_sheinbox.reset_index()
        
        stats_outbound = df2.groupby('DeviceCode').agg({
            'ShipmentContainerNumber': 'count',
            'TimeDifference_Seconds': ['mean', 'max', 'min']
        }).round(2)
        
        # Renomeia as colunas para nomes simples
        stats_outbound.columns = [
            'count',
            'mean_seconds',
            'max_seconds',
            'min_seconds'
        ]
        stats_outbound = stats_outbound.reset_index()
 
        # Adiciona colunas formatadas para tempo em horas:minutos
        for df in [stats_sheinbox, stats_outbound]:
            df['avg_time'] = pd.to_timedelta(df['mean_seconds'], unit='s').apply(
                lambda x: f"{x.components.hours:02d}:{x.components.minutes:02d}")
            df['max_time'] = pd.to_timedelta(df['max_seconds'], unit='s').apply(
                lambda x: f"{x.components.hours:02d}:{x.components.minutes:02d}")
            df['min_time'] = pd.to_timedelta(df['min_seconds'], unit='s').apply(
                lambda x: f"{x.components.hours:02d}:{x.components.minutes:02d}")
 
        # Verifica se há dados
        if df1.empty and df2.empty:
            return {
                'status': 'no_data',
                'message': 'Nenhum caso de overtime (>2h) encontrado no momento.',
                'sheinbox': [],
                'outbound': [],
                'stats_sheinbox': [],
                'stats_outbound': []
            }
 
        # Adiciona tempo formatado para os registros individuais
        for df in [df1, df2]:
            df['time_formatted'] = pd.to_timedelta(df['TimeDifference_Seconds'], unit='s').apply(
                lambda x: f"{x.components.hours:02d}:{x.components.minutes:02d}"
            )
 
        # Converte os DataFrames para listas de dicionários
        data_sheinbox = df1.to_dict(orient='records')
        data_outbound = df2.to_dict(orient='records')
        stats_sheinbox_dict = stats_sheinbox.to_dict(orient='records')
        stats_outbound_dict = stats_outbound.to_dict(orient='records')
 
        # Calcula totais gerais
        total_stats = {
            'total_overtime_cases': len(df1) + len(df2),
            'total_sheinbox_cases': len(df1),
            'total_outbound_cases': len(df2),
            'avg_time_all': pd.to_timedelta(
                pd.concat([df1['TimeDifference_Seconds'], df2['TimeDifference_Seconds']]).mean(),
                unit='s'
            ).components
        }
 
        return {
            'status': 'success',
            'sheinbox': data_sheinbox,
            'outbound': data_outbound,
            'stats_sheinbox': stats_sheinbox_dict,
            'stats_outbound': stats_outbound_dict,
            'total_stats': total_stats
        }
 
    except pyodbc.Error as e:
        return {
            'status': 'db_error',
            'message': f"Erro na conexão com o banco de dados: {str(e)}",
            'sheinbox': [],
            'outbound': [],
            'stats_sheinbox': [],
            'stats_outbound': []
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f"Erro inesperado: {str(e)}",
            'sheinbox': [],
            'outbound': [],
            'stats_sheinbox': [],
            'stats_outbound': []
        }
    finally:
        if 'conn' in locals():
            conn.close()

# Função para emitir atualizações periódicas para um dispositivo específico
def device_background_thread(device_code):
    while True:
        data = get_warehouse_data(device_code)
        socketio.emit(f'update_{device_code}', data)
        time.sleep(60)  # Atualiza a cada minuto

# Função para emitir atualizações periódicas para overtime
def overtime_background_thread():
    while True:
        data = get_overtime_data()
        socketio.emit('update_overtime', data)
        time.sleep(60)  # Atualiza a cada minuto

# Dicionário para controlar as threads ativas
active_threads = {}

@socketio.on('connect')
def handle_connect():
    print('Cliente conectado')

@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')

@socketio.on('start_device_updates')
def handle_start_device_updates(device_code):
    if device_code not in active_threads:
        thread = threading.Thread(target=device_background_thread, args=(device_code,))
        thread.daemon = True
        thread.start()
        active_threads[device_code] = thread
        print(f'Iniciando atualizações para {device_code}')

@socketio.on('start_overtime_updates')
def handle_start_overtime_updates():
    if 'overtime' not in active_threads:
        thread = threading.Thread(target=overtime_background_thread)
        thread.daemon = True
        thread.start()
        active_threads['overtime'] = thread
        print('Iniciando atualizações de overtime')

# Rota inicial
@app.route('/')
def index():
    return render_template('menu.html')

# Rota dinâmica para os sorters
@app.route('/<device_code>')
def device_route(device_code):
    if re.match(r'^BRRC(0[1-9]|10)$', device_code):
        sorter_number = int(device_code[4:]) if device_code == "BRRC10" else int(device_code[5:])
        if 1 <= sorter_number <= 10:
            data = get_warehouse_data(device_code)
            
            if data.get('status') in ['db_error', 'error']:
                return render_template('error.html', 
                                     error_message=data['message'],
                                     device_code=device_code)
            
            if data.get('status') == 'no_data':
                return render_template('no_data.html',
                                     message=data['message'],
                                     device_code=device_code)
            
            template_name = f'{device_code}.html'
            return render_template(template_name, 
                                 data=data,
                                 device_code=device_code)
            
    return render_template('not_found.html'), 404

# Rota para overtime
@app.route('/overtime')
def overtime():
    data = get_overtime_data()
    
    if data.get('status') in ['db_error', 'error']:
        return render_template('error.html', 
                             error_message=data['message'])
    
    if data.get('status') == 'no_data':
        return render_template('no_data.html',
                             message=data['message'])
    
    return render_template('overtime.html', data=data)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
