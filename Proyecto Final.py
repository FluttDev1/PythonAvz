"""
Sistema de Gestion de Tareas
----------------------------

"""

import sys
import sqlite3
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import threading
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLineEdit, QComboBox,
                            QLabel, QListWidget, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QThread

# Decorador para medir el tiempo de ejecucion
def measure_time(func):
    """Decorador que mide el tiempo de ejecucion de una funcion."""
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        result = func(*args, **kwargs)
        end_time = datetime.now()
        print(f"Funcion {func.__name__} tomo {end_time - start_time}")
        return result
    return wrapper

@dataclass
class Task:
    """Clase que representa una tarea."""
    id: Optional[int]
    title: str
    description: str
    category: str
    status: str
    created_at: datetime

class DatabaseManager:
    """Clase para manejar las operaciones de la base de datos."""
    
    def __init__(self):
        """Inicializa la conexion a la base de datos."""
        self.conn = sqlite3.connect('tasks.db')
        self.create_tables()
    
    def create_tables(self):
        """Crea las tablas necesarias si no existen."""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT,
            created_at TIMESTAMP
        )
        ''')
        self.conn.commit()

    @measure_time
    def add_task(self, task: Task) -> int:
        """Añade una nueva tarea a la base de datos."""
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO tasks (title, description, category, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (task.title, task.description, task.category, task.status,
                task.created_at.isoformat()))
        self.conn.commit()
        return cursor.lastrowid

    def get_all_tasks(self) -> List[Task]:
        """Obtiene todas las tareas de la base de datos."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM tasks')
        return [Task(id=row[0], title=row[1], description=row[2],
                    category=row[3], status=row[4],
                    created_at=datetime.fromisoformat(row[5]))
                for row in cursor.fetchall()]
    
    def update_task(self, task: Task):
        """Actualiza una tarea existente."""
        cursor = self.conn.cursor()
        cursor.execute('''
        UPDATE tasks
        SET title=?, description=?, category=?, status=?
        WHERE id=?
        ''', (task.title, task.description, task.category, task.status, task.id))
        self.conn.commit()

    def delete_task(self, task_id: int):
        """Elimina una tarea por su ID."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        self.conn.commit()

    def search_tasks(self, query: str) -> List[Task]:
        """Busca tareas que coincidan con la consulta."""
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT * FROM tasks
        WHERE title LIKE ? OR description LIKE ?
        ''', (f'%{query}%', f'%{query}%'))
        return [Task(id=row[0], title=row[1], description=row[2],
                    category=row[3], status=row[4],
                    created_at=datetime.fromisoformat(row[5]))
                for row in cursor.fetchall()]
    
class TaskWorker(QThread):
    """Clase worker para operaciones asincronas."""
    finished = pyqtSignal(list)

    def __init__(self, db_manager: DatabaseManager, operation, *args):
        super().__init__()
        self.db_manager = db_manager
        self.operation = operation
        self.args = args

    def run(self):
        """Ejecuta la operación en un hilo separado."""
        result = self.operation(*self.args)
        self.finished.emit([result] if not isinstance(result, list) else result)

class TaskManagerUI(QMainWindow):
    """Clase principal de la interfaz de usuario."""

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.init_ui()
        self.load_tasks()

    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        self.setWindowTitle('Gestor de Tareas')
        self.setGeometry(100, 100, 800, 600)

        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Barra de busqueda
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Buscar tareas...')
        self.search_input.textChanged.connect(self.search_tasks)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Lista de tareas
        self.task_list = QListWidget()
        self.task_list.itemDoubleClicked.connect(self.edit_task)
        layout.addWidget(self.task_list)

        # Botones
        button_layout = QHBoxLayout()
        add_button = QPushButton('Añadir Tarea')
        add_button.clicked.connect(self.add_task)
        delete_button = QPushButton('Eliminar Tarea')
        delete_button.clicked.connect(self.delete_task)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(delete_button)
        layout.addLayout(button_layout)

    def load_tasks(self):
        """Carga las tareas desde la base de datos."""
        worker = TaskWorker(self.db_manager, self.db_manager.get_all_tasks)
        worker.finished.connect(self.update_task_list)
        worker.start()

    def update_task_list(self, tasks: List[Task]):
        """Actualiza la lista de tareas en la UI."""
        self.task_list.clear()
        for task in tasks:
            self.task_list.addItem(
                f"{task.id}: {task.title} - {task.category} [{task.status}]")

    def add_task(self):
        """Añade una nueva tarea."""
        title, ok = QInputDialog.getText(self, 'Nueva Tarea', 'Titulo:')
        if ok and title:
            description, ok = QInputDialog.getText(
                self, 'Nueva Tarea', 'Descripcion:')
            if ok:
                category, ok = QInputDialog.getText(
                    self, 'Nueva Tarea', 'Categoria:')
                if ok:
                    task = Task(None, title, description, category, 'Pendiente',
                            datetime.now())
                    worker = TaskWorker(self.db_manager,
                                    self.db_manager.add_task, task)
                    worker.finished.connect(lambda _: self.load_tasks())
                    worker.start()

    def edit_task(self, item):
        """Edita una tarea existente."""
        task_id = int(item.text().split(':')[0])
        tasks = self.db_manager.get_all_tasks()
        task = next((t for t in tasks if t.id == task_id), None)
        
        if task:
            title, ok = QInputDialog.getText(
                self, 'Editar Tarea', 'Titulo:', text=task.title)
            if ok:
                description, ok = QInputDialog.getText(
                    self, 'Editar Tarea', 'Descripcion:',
                    text=task.description)
                if ok:
                    category, ok = QInputDialog.getText(
                        self, 'Editar Tarea', 'Categoria:',
                        text=task.category)
                    if ok:
                        updated_task = Task(task.id, title, description,
                                        category, task.status,
                                        task.created_at)
                        worker = TaskWorker(self.db_manager,
                                        self.db_manager.update_task,
                                        updated_task)
                        worker.finished.connect(lambda _: self.load_tasks())
                        worker.start()

    def delete_task(self):
        """Elimina la tarea seleccionada."""
        current_item = self.task_list.currentItem()
        if current_item:
            task_id = int(current_item.text().split(':')[0])
            reply = QMessageBox.question(
                self, 'Confirmar Eliminacion',
                '¿Estas seguro de que quieres eliminar esta tarea?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                worker = TaskWorker(self.db_manager,
                                self.db_manager.delete_task, task_id)
                worker.finished.connect(lambda _: self.load_tasks())
                worker.start()

    def search_tasks(self, query: str):
        """Busca tareas que coincidan con la consulta."""
        if query.strip():
            worker = TaskWorker(self.db_manager,
                            self.db_manager.search_tasks, query)
            worker.finished.connect(self.update_task_list)
            worker.start()
        else:
            self.load_tasks()

def main():
    """Función principal para iniciar la aplicacion."""
    app = QApplication(sys.argv)
    window = TaskManagerUI()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
