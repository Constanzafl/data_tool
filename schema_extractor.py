"""
Fase 1: Extractor de Esquema de Base de Datos
Extrae información de tablas, columnas y tipos de datos
"""

import sqlite3
import psycopg2
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import json

@dataclass
class Column:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_ref: Optional[str] = None
    unique: bool = False
    default_value: Optional[str] = None

@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: Dict[str, str] = field(default_factory=dict)  # column -> reference
    row_count: int = 0
    
    def get_column(self, name: str) -> Optional[Column]:
        for col in self.columns:
            if col.name == name:
                return col
        return None

class SchemaExtractor:
    def __init__(self, db_type: str = "sqlite", connection_params: dict = None):
        """
        Args:
            db_type: "sqlite" o "postgresql"
            connection_params: Dict con parámetros de conexión
        """
        self.db_type = db_type
        self.connection_params = connection_params or {}
        self.connection = None
        self.tables: Dict[str, Table] = {}
    
    def connect(self):
        """Establece conexión con la base de datos"""
        if self.db_type == "sqlite":
            self.connection = sqlite3.connect(
                self.connection_params.get('database', ':memory:')
            )
        elif self.db_type == "postgresql":
            self.connection = psycopg2.connect(
                host=self.connection_params.get('host', 'localhost'),
                database=self.connection_params.get('database'),
                user=self.connection_params.get('user'),
                password=self.connection_params.get('password'),
                port=self.connection_params.get('port', 5432)
            )
    
    def extract_schema(self) -> Dict[str, Table]:
        """Extrae el esquema completo de la base de datos"""
        self.connect()
        
        if self.db_type == "sqlite":
            self._extract_sqlite_schema()
        elif self.db_type == "postgresql":
            self._extract_postgresql_schema()
        
        # Extraer conteos de filas
        self._get_row_counts()
        
        return self.tables
    
    def _extract_sqlite_schema(self):
        """Extrae esquema de SQLite"""
        cursor = self.connection.cursor()
        
        # Obtener lista de tablas
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        table_names = [row[0] for row in cursor.fetchall()]
        
        for table_name in table_names:
            table = Table(name=table_name)
            
            # Obtener información de columnas
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            for col_info in columns_info:
                column = Column(
                    name=col_info[1],
                    data_type=col_info[2],
                    is_nullable=not col_info[3],
                    default_value=col_info[4],
                    is_primary_key=bool(col_info[5])
                )
                table.columns.append(column)
                
                if column.is_primary_key:
                    table.primary_keys.append(column.name)
            
            # Obtener foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fk_info = cursor.fetchall()
            
            for fk in fk_info:
                from_col = fk[3]
                to_table = fk[2]
                to_col = fk[4]
                
                table.foreign_keys[from_col] = f"{to_table}.{to_col}"
                col = table.get_column(from_col)
                if col:
                    col.is_foreign_key = True
                    col.foreign_key_ref = f"{to_table}.{to_col}"
            
            self.tables[table_name] = table
    
    def _extract_postgresql_schema(self):
        """Extrae esquema de PostgreSQL"""
        cursor = self.connection.cursor()
        
        # Obtener lista de tablas
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_names = [row[0] for row in cursor.fetchall()]
        
        for table_name in table_names:
            table = Table(name=table_name)
            
            # Obtener información de columnas
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns_info = cursor.fetchall()
            
            for col_info in columns_info:
                column = Column(
                    name=col_info[0],
                    data_type=col_info[1],
                    is_nullable=(col_info[2] == 'YES'),
                    default_value=col_info[3]
                )
                table.columns.append(column)
            
            # Obtener primary keys
            cursor.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                    AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = %s::regclass
                AND i.indisprimary
            """, (table_name,))
            
            pk_cols = cursor.fetchall()
            for pk in pk_cols:
                col_name = pk[0]
                table.primary_keys.append(col_name)
                col = table.get_column(col_name)
                if col:
                    col.is_primary_key = True
            
            # Obtener foreign keys
            cursor.execute("""
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = %s
            """, (table_name,))
            
            fk_info = cursor.fetchall()
            for fk in fk_info:
                from_col = fk[0]
                to_table = fk[1]
                to_col = fk[2]
                
                table.foreign_keys[from_col] = f"{to_table}.{to_col}"
                col = table.get_column(from_col)
                if col:
                    col.is_foreign_key = True
                    col.foreign_key_ref = f"{to_table}.{to_col}"
            
            self.tables[table_name] = table
    
    def _get_row_counts(self):
        """Obtiene el conteo de filas para cada tabla"""
        cursor = self.connection.cursor()
        
        for table_name, table in self.tables.items():
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                table.row_count = cursor.fetchone()[0]
            except:
                table.row_count = 0
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """Obtiene datos de muestra de una tabla"""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return pd.read_sql_query(query, self.connection)
    
    def export_schema(self, filename: str = "schema.json"):
        """Exporta el esquema a JSON"""
        schema_dict = {}
        
        for table_name, table in self.tables.items():
            schema_dict[table_name] = {
                "columns": [
                    {
                        "name": col.name,
                        "type": col.data_type,
                        "nullable": col.is_nullable,
                        "primary_key": col.is_primary_key,
                        "foreign_key": col.is_foreign_key,
                        "foreign_key_ref": col.foreign_key_ref
                    }
                    for col in table.columns
                ],
                "primary_keys": table.primary_keys,
                "foreign_keys": table.foreign_keys,
                "row_count": table.row_count
            }
        
        with open(filename, 'w') as f:
            json.dump(schema_dict, f, indent=2)
    
    def print_schema_summary(self):
        """Imprime un resumen del esquema"""
        print(f"\n{'='*60}")
        print(f"RESUMEN DEL ESQUEMA DE BASE DE DATOS")
        print(f"{'='*60}")
        print(f"Total de tablas: {len(self.tables)}")
        
        for table_name, table in self.tables.items():
            print(f"\n📊 Tabla: {table_name}")
            print(f"   Columnas: {len(table.columns)}")
            print(f"   Filas: {table.row_count:,}")
            
            if table.primary_keys:
                print(f"   🔑 Primary Keys: {', '.join(table.primary_keys)}")
            
            if table.foreign_keys:
                print(f"   🔗 Foreign Keys:")
                for col, ref in table.foreign_keys.items():
                    print(f"      - {col} → {ref}")
            
            print(f"\n   Columnas:")
            for col in table.columns[:5]:  # Mostrar primeras 5 columnas
                pk = "🔑" if col.is_primary_key else ""
                fk = "🔗" if col.is_foreign_key else ""
                print(f"      - {col.name} ({col.data_type}) {pk}{fk}")
            
            if len(table.columns) > 5:
                print(f"      ... y {len(table.columns) - 5} columnas más")

# Ejemplo de uso
if __name__ == "__main__":
    # Para SQLite
    extractor = SchemaExtractor(
        db_type="sqlite",
        connection_params={"database": "example.db"}
    )
    
    # Para PostgreSQL
    # extractor = SchemaExtractor(
    #     db_type="postgresql",
    #     connection_params={
    #         "host": "localhost",
    #         "database": "mydb",
    #         "user": "user",
    #         "password": "password"
    #     }
    # )
    
    # Extraer esquema
    schema = extractor.extract_schema()
    
    # Mostrar resumen
    extractor.print_schema_summary()
    
    # Exportar a JSON
    extractor.export_schema("mi_esquema.json")
    
    # Obtener datos de muestra
    # sample = extractor.get_sample_data("customers", limit=3)
    # print(sample)