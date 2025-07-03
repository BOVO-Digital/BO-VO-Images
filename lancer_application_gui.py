# lancer_application_gui.py
# Version "Production Ready" - Gestion des Fichiers Statiques
#
# Fonctionnalités :
#   - AJOUT: Onglet "Actions de Production" pour lancer collectstatic.
#   - MODIFICATION: La commande "Démarrer Backend" exécute maintenant `collectstatic` avant de lancer.
#   - MODIFICATION: Utilise `waitress` comme serveur de production pour le backend au lieu de `runserver`.

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import subprocess
import os
import re
import time
import threading

class ServiceManager(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Gestionnaire de Services d'Application (Mode Production)")
        self.geometry("950x650") # Augmentation de la hauteur

        self.pid_dir = None
        self.log_dir = None
        self.is_configured = False
        self.backend_env = None

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.toggle_controls('init')

    # ... (les fonctions de gestion de PID et de logs restent identiques) ...
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

        # --- Étape 1: Configuration du Projet ---
        path_frame = ttk.LabelFrame(main_frame, text="Étape 1: Configuration du Projet", padding=10); path_frame.pack(fill="x", pady=5); path_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(path_frame, text="Dossier Racine :").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.install_root_var = tk.StringVar()
        entry = ttk.Entry(path_frame, textvariable=self.install_root_var, state="readonly", width=80); entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ttk.Button(path_frame, text="Parcourir...", command=self.select_install_root); self.browse_button.grid(row=0, column=2, padx=5, pady=5)
        
        # --- Onglets pour les actions ---
        notebook = ttk.Notebook(main_frame); notebook.pack(fill="both", expand=True, pady=10)
        
        ports_tab = ttk.Frame(notebook, padding=10); notebook.add(ports_tab, text="Configuration des Ports")
        prod_actions_tab = ttk.Frame(notebook, padding=10); notebook.add(prod_actions_tab, text="Actions de Production")
        services_tab = ttk.Frame(notebook, padding=10); notebook.add(services_tab, text="Contrôle des Services")
        
        # --- Contenu Onglet Ports ---
        self.backend_port_var = tk.StringVar(value="8000"); self.frontend_port_var = tk.StringVar(value="3000")
        ttk.Label(ports_tab, text="Port Backend (via Waitress):").grid(row=0, column=0, padx=5, pady=5)
        self.backend_port_entry = ttk.Entry(ports_tab, textvariable=self.backend_port_var, width=10); self.backend_port_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(ports_tab, text="Port Frontend (via http.server):").grid(row=0, column=2, padx=5, pady=5)
        self.frontend_port_entry = ttk.Entry(ports_tab, textvariable=self.frontend_port_var, width=10); self.frontend_port_entry.grid(row=0, column=3, padx=5, pady=5)
        self.apply_ports_button = ttk.Button(ports_tab, text="Appliquer les Ports", command=self.apply_ports); self.apply_ports_button.grid(row=0, column=4, padx=20, pady=5)

        # --- Contenu Onglet Actions de Production ---
        ttk.Label(prod_actions_tab, text="Ces actions préparent le backend pour la production.").pack(anchor='w', pady=5)
        self.collectstatic_button = ttk.Button(prod_actions_tab, text="Lancer 'collectstatic'", command=self.run_collectstatic_manually); self.collectstatic_button.pack(anchor='w', pady=10)
        self.output_log = scrolledtext.ScrolledText(prod_actions_tab, height=8, state='disabled', wrap=tk.WORD, font=("Consolas", 9)); self.output_log.pack(fill='x', expand=True)

        # --- Contenu Onglet Contrôle des Services ---
        self.service_widgets = {}
        services = {"backend": "Backend (Waitress)", "frontend": "Frontend (http.server)", "worker": "Celery Worker", "beat": "Celery Beat"}
        services_tab.grid_columnconfigure(1, weight=1)
        for i, (key, name) in enumerate(services.items()):
            ttk.Label(services_tab, text=name, font=("Segoe UI", 10, "bold")).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            status_label = ttk.Label(services_tab, text="Inactif", foreground="grey", font=("Segoe UI", 10)); status_label.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            start_button = ttk.Button(services_tab, text="Démarrer", command=lambda k=key: self.start_service(k)); start_button.grid(row=i, column=2, padx=5, pady=5)
            stop_button = ttk.Button(services_tab, text="Arrêter", command=lambda k=key: self.stop_service(k)); stop_button.grid(row=i, column=3, padx=5, pady=5)
            view_log_button = ttk.Button(services_tab, text="Voir Log", command=lambda k=key: self.view_log(k)); view_log_button.grid(row=i, column=4, padx=5, pady=5)
            self.service_widgets[key] = {'status': status_label, 'start': start_button, 'stop': stop_button, 'view_log': view_log_button}

    def toggle_controls(self, state_key):
        if state_key == 'init':
            self.apply_ports_button.config(state='disabled')
            self.backend_port_entry.config(state='disabled')
            self.frontend_port_entry.config(state='disabled')
            self.collectstatic_button.config(state='disabled')
            for widgets in self.service_widgets.values():
                for btn in ['start', 'stop', 'view_log']: widgets[btn].config(state='disabled')
        elif state_key == 'path_ok':
            self.apply_ports_button.config(state='normal')
            self.backend_port_entry.config(state='normal')
            self.frontend_port_entry.config(state='normal')
            self.collectstatic_button.config(state='normal')
            self.sync_ui_with_pids()
    
    # ... (select_install_root, validate_and_setup_paths, etc. restent quasi-identiques) ...
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
        errors = [f"- Dossier '{name}' introuvable." for name, path in {"backend":self.backend_dir, "frontend/dist": self.frontend_build_dir}.items() if not os.path.isdir(path)]
        errors.extend([f"- Fichier essentiel '{name}' introuvable." for name, path in {"venv":self.python_venv, "backend/.env": self.backend_env_file}.items() if not os.path.exists(path)])
        if errors: messagebox.showerror("Chemins Invalides", "Impossible de configurer le projet :\n\n" + "\n".join(errors)); return False
        self.load_backend_env_vars(); return True
    
    def load_backend_env_vars(self):
        self.backend_env = os.environ.copy()
        with open(self.backend_env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#') and '=' in line: key, value = line.split('=', 1); self.backend_env[key.strip()] = value.strip().strip("'\"")

    def read_ports_from_files(self):
        try:
            with open(self.frontend_env_file, 'r') as f: content = f.read(); match = re.search(r'VITE_API_BASE_URL\s*=\s*https?://[^:]+:(\d+)', content); self.backend_port_var.set(match.group(1))
        except IOError: pass
        try:
            with open(self.backend_env_file, 'r') as f: content = f.read(); match = re.search(r'CORS_ALLOWED_ORIGINS\s*=\s*https?://[^:]+:(\d+)', content); self.frontend_port_var.set(match.group(1))
        except IOError: pass

    def apply_ports(self):
        try: b_port, f_port = int(self.backend_port_var.get()), int(self.frontend_port_var.get())
        except ValueError: messagebox.showerror("Port Invalide", "Veuillez entrer des numéros de port valides."); return
        try:
            # Gestion du .env.local
            content = f"VITE_API_BASE_URL=http://127.0.0.1:{b_port}/api\n"
            if os.path.exists(self.frontend_env_file):
                with open(self.frontend_env_file, 'r') as f: lines = f.readlines()
                line_found = False
                with open(self.frontend_env_file, 'w') as f:
                    for line in lines:
                        if line.strip().startswith('VITE_API_BASE_URL'): f.write(content); line_found = True
                        else: f.write(line)
                    if not line_found: f.write(content)
            else:
                with open(self.frontend_env_file, 'w') as f: f.write(content)
            # Gestion du .env du backend
            with open(self.backend_env_file, 'r') as f: lines = f.readlines()
            with open(self.backend_env_file, 'w') as f:
                for line in lines: f.write(f"CORS_ALLOWED_ORIGINS=http://localhost:{f_port},http://127.0.0.1:{f_port}\n" if line.strip().startswith('CORS_ALLOWED_ORIGINS') else line)
            messagebox.showinfo("Succès", "Fichiers de configuration mis à jour."); self.load_backend_env_vars()
        except Exception as e: messagebox.showerror("Erreur d'écriture", f"Impossible de mettre à jour les fichiers de configuration.\n{e}")

    ### MODIFICATION: Commande backend utilise maintenant `waitress`
    def get_command(self, service_key):
        b_port = self.backend_port_var.get()
        f_port = self.frontend_port_var.get()
        return {
            "backend": ([self.python_venv, "-m", "waitress", f"--port={b_port}", "core.wsgi:application"], self.backend_dir, self.backend_env),
            "frontend": ([self.python_venv, "-m", "http.server", f_port], self.frontend_build_dir, None),
            "worker": ([self.python_venv, "-m", "celery", "-A", "core", "worker", "-l", "info", "-P", "eventlet"], self.backend_dir, self.backend_env),
            "beat": ([self.python_venv, "-m", "celery", "-A", "core", "beat", "-l", "info", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"], self.backend_dir, self.backend_env),
        }.get(service_key)

    ### AJOUT: Exécution de commandes avec retour dans l'UI
    def _run_command_in_thread(self, command, cwd, description):
        def task():
            self.output_log.config(state='normal')
            self.output_log.delete('1.0', tk.END)
            self.output_log.insert(tk.END, f"--- Exécution de '{description}' ---\n\n")
            self.update_idletasks()
            try:
                si = subprocess.STARTUPINFO(); si.wShowWindow = subprocess.SW_HIDE; si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                process = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True, env=self.backend_env, startupinfo=si)
                self.output_log.insert(tk.END, process.stdout)
                self.output_log.insert(tk.END, f"\n--- Commande '{description}' terminée avec succès ---")
            except subprocess.CalledProcessError as e:
                self.output_log.insert(tk.END, e.stdout + e.stderr)
                self.output_log.insert(tk.END, f"\n--- ERREUR lors de l'exécution de '{description}' ---")
            except Exception as e:
                self.output_log.insert(tk.END, f"Erreur fatale: {e}")
            self.output_log.config(state='disabled')
        
        threading.Thread(target=task, daemon=True).start()

    def run_collectstatic_manually(self):
        command = [self.python_venv, "manage.py", "collectstatic", "--noinput"]
        self._run_command_in_thread(command, self.backend_dir, "collectstatic")

    def start_service(self, key):
        if key == "backend":
            # Exécute collectstatic avant de lancer le backend
            if messagebox.askyesno("Action de Production", "Lancer 'collectstatic' avant de démarrer le serveur backend ?\n(Recommandé pour s'assurer que les CSS/JS sont à jour)", default='yes'):
                command = [self.python_venv, "manage.py", "collectstatic", "--noinput"]
                try:
                    si = subprocess.STARTUPINFO(); si.wShowWindow = subprocess.SW_HIDE; si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.run(command, cwd=self.backend_dir, check=True, capture_output=True, env=self.backend_env, startupinfo=si)
                    messagebox.showinfo("Collectstatic", "Les fichiers statiques ont été collectés avec succès.")
                except subprocess.CalledProcessError as e:
                    messagebox.showerror("Erreur Collectstatic", f"Échec de collectstatic. Le serveur ne démarrera pas.\n\nErreur:\n{e.stderr.decode('utf-8', 'ignore')}")
                    return
        
        command, cwd, env = self.get_command(key)
        log_file_path = self._get_log_path(key)
        try:
            with open(log_file_path, 'wb') as log_file:
                si = subprocess.STARTUPINFO(); si.wShowWindow = subprocess.SW_HIDE; si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=log_file, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP, startupinfo=si)
            
            time.sleep(1.5)
            if self.is_process_running(proc.pid): self._write_pid(key, proc.pid)
            else: messagebox.showerror("Échec du Démarrage", f"Le service '{key}' n'a pas pu démarrer. Consultez le fichier de log.")
        except Exception as e: messagebox.showerror("Erreur", f"Erreur lors du lancement de '{key}':\n{e}")
        self.sync_ui_with_pids()

    # ... (stop_service, view_log, on_close restent identiques) ...
    def stop_service(self, key):
        pid = self._read_pid(key)
        if pid:
            try: subprocess.run(f"taskkill /F /PID {pid} /T", check=True, capture_output=True)
            except subprocess.CalledProcessError: pass
            self._delete_pid(key)
        self.sync_ui_with_pids()
    def view_log(self, key):
        log_path = self._get_log_path(key)
        if os.path.exists(log_path):
            try: os.startfile(log_path)
            except Exception as e: messagebox.showerror("Erreur", f"Impossible d'ouvrir le fichier de log:\n{e}")
        else: messagebox.showinfo("Info", "Le fichier de log n'existe pas encore. Démarrez le service d'abord.")
    def on_close(self): self.destroy()

if __name__ == "__main__":
    app = ServiceManager()
    app.mainloop()
