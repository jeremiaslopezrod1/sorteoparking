import sqlite3
import pandas as pd
import os
from datetime import datetime

def exportar_reporte_sorteo(sorteo_id=None):
    db_path = 'sorteoparking.db'
    conn = sqlite3.connect(db_path)
    
    # Si no se pasa ID, listar sorteos disponibles
    if not sorteo_id:
        df_sorteos = pd.read_sql_query("""
            SELECT s.id, t.nombre AS conjunto, s.estado, s.tipo, s.created_at
            FROM sorteos s
            JOIN tenants t ON s.tenant_id = t.id
            ORDER BY s.created_at DESC
        """, conn)
        print("Sorteos disponibles:")
        print(df_sorteos.to_string(index=False))
        sorteo_id = input("\nIngrese el ID del sorteo a exportar: ")
    
    # Consulta principal con las columnas reales
    query = """
    SELECT 
        p.apartamento,
        p.nombre AS participante,
        p.documento,
        p.whatsapp,
        p.email,
        CASE WHEN p.es_hatchback = 1 THEN 'Sí' ELSE 'No' END AS hatchback,
        p.tipo_vehiculo,
        rs.tipo_resultado,
        rs.parqueadero_asignado,
        rs.zona_asignada,
        CASE WHEN rs.fue_reasignado = 1 THEN 'Sí' ELSE 'No' END AS reasignado,
        CASE WHEN rs.notificado_por_whatsapp = 1 THEN 'Sí' ELSE 'No' END AS notificado_whatsapp,
        s.estado AS estado_sorteo,
        s.tipo AS tipo_sorteo,
        s.modelo_aplicado,
        t.nombre AS conjunto
    FROM resultados_sorteo rs
    JOIN participantes p ON rs.participante_id = p.id
    JOIN sorteos s ON rs.sorteo_id = s.id
    JOIN tenants t ON s.tenant_id = t.id
    WHERE rs.sorteo_id = ?
    ORDER BY p.apartamento
    """
    
    df = pd.read_sql_query(query, conn, params=(int(sorteo_id),))
    
    if df.empty:
        print("No hay resultados para ese sorteo.")
        conn.close()
        return
    
    # Crear carpeta EXPORTACIONES
    os.makedirs('exportaciones', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f'exportaciones/reporte_sorteo_{sorteo_id}_{timestamp}.xlsx'
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Hoja principal con todos los participantes
        df.to_excel(writer, sheet_name='Participantes', index=False)
        
        # Hoja de ganadores
        ganadores = df[df['tipo_resultado'] == 'GANADOR']
        if not ganadores.empty:
            ganadores.to_excel(writer, sheet_name='Ganadores', index=False)
        
        # Hoja de no asignados
        no_asignados = df[df['tipo_resultado'] == 'NO_ASIGNADO']
        if not no_asignados.empty:
            no_asignados.to_excel(writer, sheet_name='No Asignados', index=False)
        
        # Hoja resumen
        resumen = pd.DataFrame({
            'Metrica': [
                'Total participantes en sorteo',
                'Ganadores (asignados)',
                'No asignados (pool)',
                'Notificados por WhatsApp',
                'Reasignados',
                'Tipo de sorteo',
                'Modelo aplicado',
                'Conjunto'
            ],
            'Valor': [
                len(df),
                len(df[df['tipo_resultado'] == 'GANADOR']),
                len(df[df['tipo_resultado'] == 'NO_ASIGNADO']),
                len(df[df['notificado_whatsapp'] == 'Si']),
                len(df[df['reasignado'] == 'Si']),
                df['tipo_sorteo'].iloc[0] if not df.empty else 'N/A',
                df['modelo_aplicado'].iloc[0] if not df.empty else 'N/A',
                df['conjunto'].iloc[0] if not df.empty else 'N/A'
            ]
        })
        resumen.to_excel(writer, sheet_name='Resumen', index=False)
    
    print(f"Reporte generado en carpeta 'exportaciones/': {filename}")
    print(f"Total participantes: {len(df)}")
    print(f"Ganadores: {len(df[df['tipo_resultado'] == 'GANADOR'])}")
    print(f"No asignados: {len(df[df['tipo_resultado'] == 'NO_ASIGNADO'])}")
    print(f"Notificados WhatsApp: {len(df[df['notificado_whatsapp'] == 'Si'])}")
    
    conn.close()

if __name__ == "__main__":
    exportar_reporte_sorteo()
