# lancer_application_gui.py
# Version Finale - Gestionnaire de Services Vraiment Détaché
#
# Rôle :
# Interface graphique complète pour configurer et gérer l'environnement
# en tant que services d'arrière-plan.
#
# Fonctionnalités :
#   - CORRECTION: Utilise CREATE_NEW_PROCESS_GROUP pour que les services survivent à la fermeture de l'UI.
#   - Configuration des ports du backend et du frontend.
#   - Mise à jour automatique des fichiers .env.
#   - Suivi de l'état des services via des fichiers .pid.
#   - Redirection des logs vers des fichiers .log avec un bouton "Voir Log".
#   - AMÉLIORATION: Crée le fichier .env.local du frontend s'il n'existe pas.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import re
import time

class ServiceManager(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Gestionnaire de Services d'Application (Mode Détaché)")
        self.geometry("950x550")

        self.pid_dir = None
        self.log_dir = None
        self.is_configured = False
        self.backend_env = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.toggle_controls('init')

    # --- Logique de gestion des PID et des Logs ---
    def _get_pid_path(self, service_key): return os.path.join(self.pid_dir, f"{service_key}.pid")
    def _get_log_path(self, service_key): return os.path.join(self.log_dir, f"{service_key}.log")

    def _write_pid(self, service_key, pid):
        with open(self._get_pid_path(service_key), 'w') as f: f.write(str(pid))

    def _read_pid(self, service_key):
        try:
            with open(self._get_pid_path(service_key), 'r') as f: return int(f.read().strip())
        except (IOError, ValueError): return None

    def _delete_pid(self, service_key):
        if os.path.exists(self._get_pid_path(service_key)): os.remove(self._get_pid_path(service_key))
    
    def is_process_running(self, pid):
        try:
            si = subprocess.STARTUPINFO(); si.wShowWindow = subprocess.SW_HIDE; si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(f'tasklist /FI "PID eq {pid}"', stderr=subprocess.STDOUT, text=True, startupinfo=si)
            return str(pid) in output
        except subprocess.CalledProcessError: return False

    def sync_ui_with_pids(self):
        if not self.is_configured: return
        for key, widgets in self.service_widgets.items():
            pid = self._read_pid(key)
            if pid and self.is_process_running(pid):
                widgets['status'].config(text=f"En cours (PID: {pid})", foreground="green")
                widgets['start'].config(state='disabled'); widgets['stop'].config(state='normal'); widgets['view_log'].config(state='normal')
            else:
                self._delete_pid(key)
                widgets['status'].config(text="Arrêté", foreground="red")
                widgets['start'].config(state='normal'); widgets['stop'].config(state='disabled'); widgets['view_log'].config(state='normal' if os.path.exists(self._get_log_path(key)) else 'disabled')

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=10); main_frame.pack(fill="both", expand=True)
        path_frame = ttk.LabelFrame(main_frame, text="Étape 1: Configuration du Projet", padding=10); path_frame.pack(fill="x", pady=5); path_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(path_frame, text="Dossier Racine :").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.install_root_var = tk.StringVar()
        entry = ttk.Entry(path_frame, textvariable=self.install_root_var, state="readonly", width=80); entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ttk.Button(path_frame, text="Parcourir...", command=self.select_install_root); self.browse_button.grid(row=0, column=2, padx=5, pady=5)
        self.port_frame = ttk.LabelFrame(main_frame, text="Étape 2: Configuration des Ports", padding=10); self.port_frame.pack(fill="x", pady=5)
        self.backend_port_var = tk.StringVar(value="8000"); self.frontend_port_var = tk.StringVar(value="3000")
        ttk.Label(self.port_frame, text="Port Backend :").grid(row=0, column=0, padx=5, pady=5)
        self.backend_port_entry = ttk.Entry(self.port_frame, textvariable=self.backend_port_var, width=10); self.backend_port_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(self.port_frame, text="Port Frontend :").grid(row=0, column=2, padx=5, pady=5)
        self.frontend_port_entry = ttk.Entry(self.port_frame, textvariable=self.frontend_port_var, width=10); self.frontend_port_entry.grid(row=0, column=3, padx=5, pady=5)
        self.apply_ports_button = ttk.Button(self.port_frame, text="Appliquer les Ports", command=self.apply_ports); self.apply_ports_button.grid(row=0, column=4, padx=20, pady=5)
        self.control_frame = ttk.LabelFrame(main_frame, text="Étape 3: Contrôle des Services", padding=10); self.control_frame.pack(fill="both", expand=True, pady=5); self.control_frame.grid_columnconfigure(1, weight=1)
        self.service_widgets = {}
        services = {"backend": "Backend", "frontend": "Frontend", "worker": "Celery Worker", "beat": "Celery Beat"}
        for i, (key, name) in enumerate(services.items()):
            ttk.Label(self.control_frame, text=name, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            status_label = ttk.Label(self.control_frame, text="Inactif", foreground="grey", font=("Segoe UI", 10)); status_label.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            start_button = ttk.Button(self.control_frame, text="Démarrer", command=lambda k=key: self.start_service(k)); start_button.grid(row=i, column=2, padx=5, pady=5)
            stop_button = ttk.Button(self.control_frame, text="Arrêter", command=lambda k=key: self.stop_service(k)); stop_button.grid(row=i, column=3, padx=5, pady=5)
            view_log_button = ttk.Button(self.control_frame, text="Voir Log", command=lambda k=key: self.view_log(k)); view_log_button.grid(row=i, column=4, padx=5, pady=5)
            self.service_widgets[key] = {'status': status_label, 'start': start_button, 'stop': stop_button, 'view_log': view_log_button}

    def toggle_controls(self, state_key):
        if state_key == 'init':
            for child in self.port_frame.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Entry)): child.config(state='disabled')
            for widgets in self.service_widgets.values():
                for btn in ['start', 'stop', 'view_log']: widgets[btn].config(state='disabled')
        elif state_key == 'path_ok':
            for child in self.port_frame.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Entry)): child.config(state='normal')
            self.sync_ui_with_pids()

    def select_install_root(self):
        path = filedialog.askdirectory(title="Sélectionnez le dossier racine de l'application")
        if path and self.validate_and_setup_paths(path):
            self.install_root_var.set(path)
            self.pid_dir = os.path.join(path, ".pids"); os.makedirs(self.pid_dir, exist_ok=True)
            self.log_dir = os.path.join(path, "logs"); os.makedirs(self.log_dir, exist_ok=True)
            self.is_configured = True
            self.read_ports_from_files()
            self.toggle_controls('path_ok')

    def validate_and_setup_paths(self, root_path):
        self.backend_dir = os.path.join(root_path, 'backend'); self.frontend_dir = os.path.join(root_path, 'frontend'); self.frontend_build_dir = os.path.join(self.frontend_dir, 'dist'); self.python_venv = os.path.join(self.backend_dir, 'venv', 'Scripts', 'python.exe'); self.backend_env_file = os.path.join(self.backend_dir, '.env'); self.frontend_env_file = os.path.join(self.frontend_dir, '.env.local')
        
        ### MODIFICATION ###: L'absence de .env.local n'est plus une erreur bloquante.
        errors = [f"- Dossier '{name}' introuvable." for name, path in {"backend":self.backend_dir, "frontend/dist": self.frontend_build_dir}.items() if not os.path.isdir(path)]
        errors.extend([f"- Fichier essentiel '{name}' introuvable." for name, path in {"venv":self.python_venv, "backend/.env": self.backend_env_file}.items() if not os.path.exists(path)])
        
        if errors:
            messagebox.showerror("Chemins Invalides", "Impossible de configurer le projet :\n\n" + "\n".join(errors)); return False
        
        self.load_backend_env_vars()
        return True
    
    def load_backend_env_vars(self):
        self.backend_env = os.environ.copy()
        with open(self.backend_env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#') and '=' in line:
                    key, value = line.split('=', 1); self.backend_env[key.strip()] = value.strip().strip("'\"")
        
    def read_ports_from_files(self):
        # La lecture est maintenant protégée pour ne pas échouer si les fichiers sont absents ou malformés.
        try:
            with open(self.frontend_env_file, 'r') as f:
                content = f.read()
                match = re.search(r'VITE_API_BASE_URL\s*=\s*https?://[^:]+:(\d+)', content)
                if match: self.backend_port_var.set(match.group(1))
        except IOError: pass # Fichier n'existe pas, on ignore.
        
        try:
            with open(self.backend_env_file, 'r') as f:
                content = f.read()
                match = re.search(r'CORS_ALLOWED_ORIGINS\s*=\s*https?://[^:]+:(\d+)', content)
                if match: self.frontend_port_var.set(match.group(1))
        except IOError: pass # Fichier n'existe pas, on ignore.

    def apply_ports(self):
        try:
            b_port, f_port = int(self.backend_port_var.get()), int(self.frontend_port_var.get())
        except ValueError:
            messagebox.showerror("Port Invalide", "Veuillez entrer des numéros de port valides."); return
        
        try:
            ### MODIFICATION ###: Crée le fichier .env.local s'il n'existe pas, sinon le met à jour.
            if os.path.exists(self.frontend_env_file):
                with open(self.frontend_env_file, 'r') as f: lines = f.readlines()
                # Cherche et remplace la ligne, sinon l'ajoute.
                line_found = False
                with open(self.frontend_env_file, 'w') as f:
                    for line in lines:
                        if line.strip().startswith('VITE_API_BASE_URL'):
                            f.write(f"VITE_API_BASE_URL=http://127.0.0.1:{b_port}/api\n")
                            line_found = True
                        else:
                            f.write(line)
                    if not line_found:
                        f.write(f"VITE_API_BASE_URL=http://127.0.0.1:{b_port}/api\n")
            else:
                # Le fichier n'existe pas, on le crée.
                with open(self.frontend_env_file, 'w') as f:
                    f.write(f"VITE_API_BASE_URL=http://127.0.0.1:{b_port}/api\n")

            # Met à jour le fichier .env du backend de la même manière.
            with open(self.backend_env_file, 'r') as f: lines = f.readlines()
            with open(self.backend_env_file, 'w') as f:
                for line in lines:
                    f.write(f"CORS_ALLOWED_ORIGINS=http://localhost:{f_port},http://127.0.0.1:{f_port}\n" if line.strip().startswith('CORS_ALLOWED_ORIGINS') else line)
            
            messagebox.showinfo("Succès", "Fichiers de configuration mis à jour.")
            self.load_backend_env_vars()
        except Exception as e:
            messagebox.showerror("Erreur d'écriture", f"Impossible de mettre à jour les fichiers de configuration.\n{e}")

    def get_command(self, service_key):
        b_port, f_port = self.backend_port_var.get(), self.frontend_port_var.get()
        return {
            "backend": ([self.python_venv, "manage.py", "runserver", b_port], self.backend_dir, self.backend_env),
            "frontend": ([self.python_venv, "-m", "http.server", f_port], self.frontend_build_dir, None),
            "worker": ([self.python_venv, "-m", "celery", "-A", "core", "worker", "-l", "info", "-P", "eventlet"], self.backend_dir, self.backend_env),
            "beat": ([self.python_venv, "-m", "celery", "-A", "core", "beat", "-l", "info", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"], self.backend_dir, self.backend_env),
        }.get(service_key)

    def start_service(self, key):
        command, cwd, env = self.get_command(key)
        log_file_path = self._get_log_path(key)
        try:
            with open(log_file_path, 'wb') as log_file:
                si = subprocess.STARTUPINFO(); si.wShowWindow = subprocess.SW_HIDE; si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                proc = subprocess.Popen(
                    command, cwd=cwd, env=env, 
                    stdout=log_file, stderr=subprocess.STDOUT, 
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, 
                    startupinfo=si
                )

            time.sleep(1.5)
            if self.is_process_running(proc.pid):
                self._write_pid(key, proc.pid)
            else:
                messagebox.showerror("Échec du Démarrage", f"Le service '{key}' n'a pas pu démarrer. Consultez le fichier de log pour plus de détails.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du lancement de '{key}':\n{e}")
        self.sync_ui_with_pids()

    def stop_service(self, key):
        pid = self._read_pid(key)
        if pid:
            try:
                subprocess.run(f"taskkill /F /PID {pid} /T", check=True, capture_output=True, text=True, startupinfo=subprocess.STARTUPINFO(wShowWindow=subprocess.SW_HIDE))
            except subprocess.CalledProcessError:
                pass # Le processus n'existe peut-être déjà plus, c'est ok.
            self._delete_pid(key)
        self.sync_ui_with_pids()

    def view_log(self, key):
        log_path = self._get_log_path(key)
        if os.path.exists(log_path):
            try:
                os.startfile(log_path)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'ouvrir le fichier de log:\n{e}")
        else:
            messagebox.showinfo("Info", "Le fichier de log n'existe pas encore. Démarrez le service d'abord.")

    def on_close(self):
        self.destroy()

if __name__ == "__main__":
    app = ServiceManager()
    app.mainloop()
