# install_rh_app_gui.py
# Version 4.5 - Correction et amélioration de la création du super-utilisateur
# - La création du super-utilisateur est désormais optionnelle via une case à cocher.
# - Correction du crash si l'email du super-utilisateur existe déjà.

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import configparser
import subprocess
import threading
import os
import sys
import shutil
import socket
import random
import string
import ctypes
from datetime import datetime
import queue
import importlib

# =============================================================================
# Classe pour stocker l'état partagé
# =============================================================================
class InstallerState:
    def __init__(self):
        self.config = {}
        self.install_path = ""

# =============================================================================
# Classe principale du Wizard
# =============================================================================
class InstallerWizard(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = InstallerState()
        
        try:
            self.load_config()
        except Exception as e:
            messagebox.showerror("Erreur Critique", f"Impossible de charger ou de lire 'config.ini'.\nErreur: {e}")
            self.destroy()
            return
            
        self.title(f"Assistant d'Installation - {self.state.config.get('app_name', 'Application')}")
        self.geometry("900x750")

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (WelcomePage, PrereqCheckPage, RepoPage, ConfigPage, InstallProgressPage, FinishPage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(WelcomePage)

    def load_config(self):
        parser = configparser.ConfigParser()
        if not os.path.exists("config.ini"):
            raise FileNotFoundError("Le fichier 'config.ini' est manquant à côté du script.")
        parser.read("config.ini")
        self.state.config['app_name'] = parser.get('Application', 'name', fallback="Application sans nom")
        self.state.config['backend_url'] = parser.get('Repositories', 'backend_url')
        self.state.config['frontend_url'] = parser.get('Repositories', 'frontend_url')

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()

# =============================================================================
# Classe de base pour les pages du Wizard
# =============================================================================
class WizardPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

# =============================================================================
# Fonctions et Widgets Utilitaires
# =============================================================================
def execute_command(command, description):
    try:
        process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', shell=True, check=True)
        return True, process.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        error_output = e.stderr if hasattr(e, 'stderr') else str(e)
        return False, f"Échec de '{description}':\n{error_output}"

class StatusLabel(ttk.Frame):
    def __init__(self, parent, text):
        super().__init__(parent)
        self.status_icon = ttk.Label(self, text="○", font=("Segoe UI", 12), width=3)
        self.status_icon.pack(side="left")
        self.label_text = text
        self.label = ttk.Label(self, text=text, font=("Segoe UI", 10))
        self.label.pack(side="left")
        self.set_status("pending")

    def set_status(self, status, text=None):
        statuses = {"pending": ("○", "gray"), "success": ("✔️", "green"), "error": ("❌", "red")}
        icon, color = statuses.get(status, statuses["pending"])
        self.status_icon.config(text=icon, foreground=color)
        if text: self.label.config(text=f"{self.label_text} ({text})")

# =============================================================================
# Page 1: Accueil
# =============================================================================
class WelcomePage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        label = ttk.Label(self, text=f"Bienvenue dans l'assistant d'installation", font=("Segoe UI", 22, "bold"))
        label.pack(pady=20, padx=20)
        app_name_label = ttk.Label(self, text=f"{controller.state.config.get('app_name')}", font=("Segoe UI", 18))
        app_name_label.pack(pady=10, padx=20)
        info_text = ("Cet assistant vous guidera à travers l'installation et la configuration de l'application.\n\n"
                     "Il est recommandé de le lancer avec des droits d'administrateur.\n\n"
                     "Assurez-vous d'avoir à portée de main :\n"
                     "   • Les informations de connexion à la base de données PostgreSQL.\n"
                     "   • Les informations de connexion à l'API BioStar 2.\n"
                     "   • Un Personal Access Token (PAT) GitHub si les dépôts sont privés.")
        info_label = ttk.Label(self, text=info_text, justify="left", font=("Segoe UI", 11))
        info_label.pack(pady=20, padx=40)
        button_frame = ttk.Frame(self)
        button_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        next_button = ttk.Button(button_frame, text="Suivant", command=lambda: controller.show_frame(PrereqCheckPage))
        next_button.pack(side="right")

# =============================================================================
# Page 2: Vérification des prérequis
# =============================================================================
class PrereqCheckPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.title = ttk.Label(self, text="Étape 1: Vérification des Prérequis", font=("Segoe UI", 16, "bold"))
        self.title.pack(pady=10)
        self.prereqs = {
            "Git": {"check_func": lambda: shutil.which("git"), "status_label": StatusLabel(self, "Git (pour le clonage)")},
            "Python": {"check_func": lambda: shutil.which("python"), "status_label": StatusLabel(self, "Python 3.x")},
            "Node.js": {"check_func": lambda: shutil.which("node"), "status_label": StatusLabel(self, "Node.js (pour le frontend)")},
            "NPM": {"check_func": lambda: shutil.which("npm"), "status_label": StatusLabel(self, "NPM (gestionnaire de paquets JS)")}
        }
        for prereq in self.prereqs.values():
            prereq["status_label"].pack(anchor="w", padx=40, pady=5)
        self.check_button = ttk.Button(self, text="Vérifier les Prérequis", command=self.check_prerequisites)
        self.check_button.pack(pady=20)
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        self.next_button = ttk.Button(self.button_frame, text="Suivant", command=lambda: controller.show_frame(RepoPage), state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(self.button_frame, text="Précédent", command=lambda: controller.show_frame(WelcomePage)).pack(side="right", padx=10)

    def check_prerequisites(self):
        all_ok = True
        for name, data in self.prereqs.items():
            if data["check_func"](): data["status_label"].set_status("success")
            else: data["status_label"].set_status("error", f"Introuvable"); all_ok = False
        if all_ok:
            self.next_button.config(state="normal")
            messagebox.showinfo("Succès", "Toutes les dépendances de base ont été trouvées.")
        else:
            messagebox.showwarning("Échec", "Certains prérequis sont manquants. Installez-les et assurez-vous qu'ils sont dans le PATH système, puis réessayez.")

# =============================================================================
# Page 3: Configuration des dépôts
# =============================================================================
class RepoPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.title = ttk.Label(self, text="Étape 2: Configuration des Dépôts", font=("Segoe UI", 16, "bold"))
        self.title.pack(pady=10)
        ttk.Label(self, text="URL du dépôt Backend:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=40, pady=(10,0))
        self.backend_url_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.backend_url_var, width=80).pack(anchor="w", padx=40, pady=5, ipady=3)
        ttk.Label(self, text="URL du dépôt Frontend:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=40, pady=(10,0))
        self.frontend_url_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.frontend_url_var, width=80).pack(anchor="w", padx=40, pady=5, ipady=3)
        ttk.Label(self, text="Personal Access Token GitHub (si dépôts privés):", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=40, pady=(10,0))
        self.pat_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.pat_var, show="*").pack(anchor="w", padx=40, pady=5, ipady=3)
        self.validate_button = ttk.Button(self, text="Valider les URLs", command=self.validate_repos)
        self.validate_button.pack(pady=20)
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        self.next_button = ttk.Button(self.button_frame, text="Suivant", command=lambda: controller.show_frame(ConfigPage), state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(self.button_frame, text="Précédent", command=lambda: controller.show_frame(PrereqCheckPage)).pack(side="right", padx=10)

    def on_show(self):
        self.backend_url_var.set(self.controller.state.config.get('backend_url', ''))
        self.frontend_url_var.set(self.controller.state.config.get('frontend_url', ''))

    def validate_repos(self):
        urls_to_check = {"Backend": self.backend_url_var.get(), "Frontend": self.frontend_url_var.get()}
        pat = self.pat_var.get()
        all_valid, errors = True, []
        for name, url in urls_to_check.items():
            if not url or "VOTRE" in url:
                errors.append(f"L'URL pour le dépôt {name} est invalide ou non configurée."); all_valid = False; continue
            url_to_validate = url
            
            if pat:
                if url.startswith("https://"):
                    domain_and_path = url[8:]
                    url_to_validate = f"https://{pat}@{domain_and_path}"
                else:
                    errors.append(f"Le PAT ne peut être injecté que dans une URL HTTPS pour le dépôt {name}."); all_valid = False; continue
            
            success, output = execute_command(f'git ls-remote --exit-code "{url_to_validate}"', f"Validation de {name}")
            if not success:
                errors.append(f"Impossible de joindre le dépôt {name}.\n   - Vérifiez l'URL et l'accès réseau.\n   - Si privé, vérifiez le PAT et ses droits ('repo').\n   - Erreur: {output}"); all_valid = False
        
        if all_valid:
            messagebox.showinfo("Succès", "Les deux URLs de dépôts sont valides et accessibles.")
            self.next_button.config(state="normal")
            self.controller.state.config['backend_url'] = self.backend_url_var.get()
            self.controller.state.config['frontend_url'] = self.frontend_url_var.get()
            self.controller.state.config['pat'] = pat
        else:
            messagebox.showerror("Échec de la validation", "\n\n".join(errors))
            self.next_button.config(state="disabled")

# =============================================================================
# Page 4: Configuration de l'environnement
# =============================================================================
class ConfigPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.title = ttk.Label(self, text="Étape 3: Configuration de l'Environnement", font=("Segoe UI", 16, "bold"))
        self.title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # --- Django ---
        django_frame = ttk.LabelFrame(self, text="Configuration Django", padding=10)
        django_frame.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="ew")
        ttk.Label(django_frame, text="Hôtes autorisés (séparés par virgule):").grid(row=0, column=0, sticky="w")
        self.allowed_hosts_var = tk.StringVar(value="localhost,127.0.0.1")
        ttk.Entry(django_frame, textvariable=self.allowed_hosts_var, width=60).grid(row=0, column=1, sticky="ew")

        # --- Super-utilisateur Django ---
        su_frame = ttk.LabelFrame(self, text="Super-utilisateur Django", padding=10)
        su_frame.grid(row=2, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        ### AJOUT ###: Case à cocher pour rendre la création optionnelle
        self.create_su_var = tk.BooleanVar(value=True)
        su_check = ttk.Checkbutton(su_frame, text="Créer un compte administrateur", variable=self.create_su_var, command=self._toggle_su_fields)
        su_check.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 10))

        self.su_vars = {
            "username": tk.StringVar(), "email": tk.StringVar(), "first_name": tk.StringVar(),
            "last_name": tk.StringVar(), "password": tk.StringVar(), "password_confirm": tk.StringVar()
        }
        
        # ### MODIFICATION ###: Stocker les widgets d'entrée pour les activer/désactiver
        self.su_entries = []

        labels_and_vars = [
            ("Nom d'utilisateur:", "username", {}),
            ("Email:", "email", {}),
            ("Prénom:", "first_name", {}),
            ("Nom (optionnel):", "last_name", {}),
            ("Mot de passe:", "password", {"show": "*"}),
            ("Confirmer le mot de passe:", "password_confirm", {"show": "*"})
        ]

        for i, (label_text, key, opts) in enumerate(labels_and_vars):
            row = i + 1
            ttk.Label(su_frame, text=label_text).grid(row=row, column=0, sticky="w", padx=5, pady=3)
            entry = ttk.Entry(su_frame, textvariable=self.su_vars[key], **opts)
            entry.grid(row=row, column=1, sticky="ew", padx=5, pady=3)
            self.su_entries.append(entry)

        su_frame.grid_columnconfigure(1, weight=1)

        # --- PostgreSQL ---
        db_frame = ttk.LabelFrame(self, text="Base de Données PostgreSQL", padding=10)
        db_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.db_vars = {"host": tk.StringVar(value="localhost"), "port": tk.IntVar(value=5432), "dbname": tk.StringVar(value="rh_app_db"), "user": tk.StringVar(value="rh_app_user"), "password": tk.StringVar()}
        labels = ["Hôte:", "Port:", "Nom de la base:", "Utilisateur:", "Mot de passe:"]
        for i, (key, text) in enumerate(zip(self.db_vars, labels)):
            show_opt = {"show": "*"} if key == "password" else {}
            ttk.Label(db_frame, text=text).grid(row=i, column=0, sticky="w", padx=5, pady=3)
            ttk.Entry(db_frame, textvariable=self.db_vars[key], **show_opt).grid(row=i, column=1, sticky="ew", padx=5, pady=3)
        self.db_test_button = ttk.Button(db_frame, text="Tester la Connexion", command=self.test_db_connection)
        self.db_test_button.grid(row=len(labels), column=1, pady=10)
        
        # --- Redis & BioStar ---
        other_frame = ttk.LabelFrame(self, text="Autres Services", padding=10)
        other_frame.grid(row=3, column=1, padx=20, pady=10, sticky="nsew")
        self.redis_port_var = tk.IntVar(value=6379)
        ttk.Label(other_frame, text="Port Redis:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(other_frame, textvariable=self.redis_port_var).grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        self.biostar_vars = {"url": tk.StringVar(), "login": tk.StringVar(), "password": tk.StringVar()}
        ttk.Label(other_frame, text="URL API BioStar 2:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(other_frame, textvariable=self.biostar_vars["url"]).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(other_frame, text="Login BioStar 2:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(other_frame, textvariable=self.biostar_vars["login"]).grid(row=2, column=1, sticky="ew", padx=5, pady=3)
        ttk.Label(other_frame, text="Mot de passe BioStar 2:").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(other_frame, textvariable=self.biostar_vars["password"], show="*").grid(row=3, column=1, sticky="ew", padx=5, pady=3)
        
        # --- Navigation ---
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=20, padx=20)
        self.next_button = ttk.Button(button_frame, text="Suivant", command=self.save_and_continue, state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(button_frame, text="Précédent", command=lambda: controller.show_frame(RepoPage)).pack(side="right", padx=10)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

    ### AJOUT ###: Méthode pour activer/désactiver les champs du super-utilisateur
    def _toggle_su_fields(self):
        new_state = "normal" if self.create_su_var.get() else "disabled"
        for entry in self.su_entries:
            entry.config(state=new_state)

    def _ensure_package(self, package_name, import_name):
        try: return importlib.import_module(import_name)
        except ImportError:
            if messagebox.askyesno( "Dépendance Manquante", f"Le module Python '{import_name}' est requis mais non installé.\nVoulez-vous tenter de l'installer (via 'pip install {package_name}') ?"):
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return importlib.import_module(import_name)
                except (subprocess.CalledProcessError, Exception) as e:
                    messagebox.showerror("Échec de l'installation", f"Impossible d'installer '{package_name}'.\Veuillez l'installer manuellement.\nErreur: {e}")
            return None

    def test_db_connection(self):
        psycopg2 = self._ensure_package('psycopg2-binary', 'psycopg2')
        if not psycopg2:
            if messagebox.askokcancel("Continuer ?", "Le test de connexion a été annulé car 'psycopg2' n'est pas disponible.\nVoulez-vous continuer sans valider ?"):
                self.next_button.config(state="normal")
            return
        try:
            conn = psycopg2.connect(dbname=self.db_vars["dbname"].get(), user=self.db_vars["user"].get(), password=self.db_vars["password"].get(), host=self.db_vars["host"].get(), port=self.db_vars["port"].get(), connect_timeout=3)
            conn.close()
            messagebox.showinfo("Succès", "Connexion à PostgreSQL réussie.")
            self.next_button.config(state="normal")
        except Exception as e:
            messagebox.showerror("Échec de la Connexion", f"Impossible de se connecter à PostgreSQL.\nVérifiez les paramètres et le pare-feu.\n\nErreur: {e}")
            self.next_button.config(state="disabled")

    def save_and_continue(self):
        config = self.controller.state.config
        
        ### MODIFICATION ###: La validation du super-utilisateur est maintenant conditionnelle
        config['create_superuser'] = self.create_su_var.get()
        if config['create_superuser']:
            su_user = self.su_vars['username'].get().strip()
            su_email = self.su_vars['email'].get().strip()
            su_pass1 = self.su_vars['password'].get()
            su_pass2 = self.su_vars['password_confirm'].get()
            su_first_name = self.su_vars['first_name'].get().strip()
            su_last_name = self.su_vars['last_name'].get().strip()

            if not all([su_user, su_email, su_pass1]):
                messagebox.showwarning("Champs Manquants", "Le nom d'utilisateur, l'email et le mot de passe du super-utilisateur sont requis.")
                return
            if su_pass1 != su_pass2:
                messagebox.showerror("Erreur de Mot de Passe", "Les mots de passe du super-utilisateur ne correspondent pas.")
                return
            if not su_first_name:
                su_first_name = su_user
                messagebox.showinfo("Information", f"Le champ 'Prénom' étant vide, il a été défini sur '{su_user}' par défaut.")
            
            config['superuser_username'] = su_user
            config['superuser_email'] = su_email
            config['superuser_password'] = su_pass1
            config['superuser_first_name'] = su_first_name
            config['superuser_last_name'] = su_last_name

        config['allowed_hosts'] = self.allowed_hosts_var.get()
        config.update({f"db_{key}": var.get() for key, var in self.db_vars.items()})
        config.update({f"biostar_{key}": var.get() for key, var in self.biostar_vars.items()})
        config['redis_port'] = self.redis_port_var.get()

        if not all([config.get('biostar_url'), config.get('biostar_login')]):
            messagebox.showwarning("Champs Manquants", "Les informations pour BioStar 2 sont requises.")
            return
            
        self.controller.show_frame(InstallProgressPage)

# =============================================================================
# Page 5: Installation
# =============================================================================
class InstallProgressPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.title = ttk.Label(self, text="Étape 4: Installation", font=("Segoe UI", 16, "bold"))
        self.title.pack(pady=10)
        self.progress = ttk.Progressbar(self, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill="x", padx=40, pady=10)
        self.log_text = tk.Text(self, wrap="none", state="disabled", font=("Consolas", 9), relief=tk.SOLID, borderwidth=1)
        self.log_text.pack(fill="both", expand=True, padx=40, pady=10)
        self.log_text.tag_configure("SUCCESS", foreground="green"); self.log_text.tag_configure("ERROR", foreground="red"); self.log_text.tag_configure("STEP", foreground="blue", font=("Consolas", 9, "bold"))
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        self.next_button = ttk.Button(self.button_frame, text="Terminer", state="disabled", command=lambda: controller.show_frame(FinishPage))
        self.next_button.pack(side="right")
        self.install_button = ttk.Button(self.button_frame, text="Lancer l'Installation", command=self.start_installation)
        self.install_button.pack(side="left")

    def on_show(self):
        self.install_button.config(state="normal"); self.next_button.config(state="disabled")

    def log(self, message, level="INFO"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n", level)
        self.log_text.config(state="disabled"); self.log_text.see("end"); self.update_idletasks()

    def _execute(self, command, description, **kwargs):
        self.log(f"Exécution: {description}...")
        try:
            subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True, shell=True, **kwargs)
            self.log(f"Succès: {description}.", "SUCCESS")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Échec de '{description}'. Erreur:\n{e.stderr or e.stdout}")

    def start_installation(self):
        self.install_button.config(state="disabled")
        install_path = filedialog.askdirectory(title="Confirmez le dossier racine d'installation")
        if not install_path:
            self.log("Installation annulée: aucun dossier sélectionné.", "ERROR"); self.install_button.config(state="normal"); return
        self.controller.state.install_path = install_path
        threading.Thread(target=self.run_install_logic, daemon=True).start()

    def run_install_logic(self):
        try:
            state = self.controller.state; config = state.config; install_path = state.install_path
            self.log("Démarrage de l'installation...")
            os.makedirs(install_path, exist_ok=True)
            
            # --- 1. Clonage ---
            self.progress['value'] = 10; self.log("Étape 1: Clonage des dépôts...", "STEP")
            full_backend_path = os.path.join(install_path, "backend"); full_frontend_path = os.path.join(install_path, "frontend")
            pat = config.get('pat')
            def build_clone_url(base_url): return f"https://{pat}@{base_url[8:]}" if pat and base_url.startswith("https://") else base_url
            for name, url, path in [("Backend", config['backend_url'], full_backend_path), ("Frontend", config['frontend_url'], full_frontend_path)]:
                if os.path.exists(os.path.join(path, ".git")): self._execute(f'git -C "{path}" pull', f"Mise à jour {name}")
                else: self._execute(f'git clone "{build_clone_url(url)}" "{path}"', f"Clonage {name}")
            
            # --- 2. Génération .env ---
            self.progress['value'] = 20; self.log("Étape 2: Génération du fichier de configuration .env...", "STEP")
            secret_key = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=60)).replace("'", "s").replace('"', 's').replace('`', 's')
            db_url = f"postgres://{config['db_user']}:{config['db_password']}@{config['db_host']}:{config['db_port']}/{config['db_dbname']}"
            env_content = (f"DJANGO_SECRET_KEY='{secret_key}'\nDJANGO_DEBUG=False\nALLOWED_HOSTS={config['allowed_hosts']}\nDATABASE_URL='{db_url}'\n"
                           f"CORS_ALLOWED_ORIGINS=http://{config['allowed_hosts'].split(',')[0].strip()}:3000,https://{config['allowed_hosts'].split(',')[0].strip()}\n"
                           f"CELERY_BROKER_URL='redis://localhost:{config['redis_port']}/0'\nCELERY_RESULT_BACKEND='redis://localhost:{config['redis_port']}/0'\n"
                           f"BIOSTAR_API_BASE_URL={config['biostar_url']}\nBIOSTAR_ADMIN_LOGIN_ID={config['biostar_login']}\n"
                           f"BIOSTAR_ADMIN_PASSWORD='{config['biostar_password']}'\n"
                           f"MOCK_BIOSTAR_API=False")
            with open(os.path.join(full_backend_path, ".env"), "w", encoding="utf-8") as f: f.write(env_content)

            # --- 3. Dépendances ---
            self.progress['value'] = 40; self.log("Étape 3: Installation des dépendances...", "STEP")
            venv_path = os.path.join(full_backend_path, "venv")
            if not os.path.exists(venv_path): self._execute(f'"{sys.executable}" -m venv "{venv_path}"', "Création de l'environnement virtuel Python")
            pip_in_venv = os.path.join(venv_path, 'Scripts', 'pip.exe')
            self._execute(f'"{pip_in_venv}" install -r requirements.txt', "Paquets Python (pip)", cwd=full_backend_path)
            self._execute('npm install', "Paquets JavaScript (npm)", cwd=full_frontend_path)
            
            # --- 4. Migrations ---
            self.progress['value'] = 70; self.log("Étape 4: Initialisation de la base de données...", "STEP")
            backend_env = {**os.environ, **{k.strip(): v.strip().strip("'\"") for k, v in [line.split('=', 1) for line in env_content.splitlines() if '=' in line]}}
            python_in_venv = os.path.join(venv_path, 'Scripts', 'python.exe')
            self._execute(f'"{python_in_venv}" manage.py migrate', "Migrations Django", cwd=full_backend_path, env=backend_env)
            
            # ### MODIFICATION ###: L'étape de création du super-utilisateur est maintenant entièrement conditionnelle
            if config.get('create_superuser', False):
                self.progress['value'] = 80; self.log("Étape 5: Création du super-utilisateur...", "STEP")
                superuser_env = {**backend_env, 'DJANGO_SUPERUSER_USERNAME': config['superuser_username'], 'DJANGO_SUPERUSER_EMAIL': config['superuser_email'],
                                 'DJANGO_SUPERUSER_PASSWORD': config['superuser_password'], 'DJANGO_SUPERUSER_FIRST_NAME': config['superuser_first_name'],
                                 'DJANGO_SUPERUSER_LAST_NAME': config['superuser_last_name']}
                try:
                    self._execute(f'"{python_in_venv}" manage.py createsuperuser --noinput', "Création du compte administrateur Django", cwd=full_backend_path, env=superuser_env)
                except Exception as e:
                    error_str = str(e).lower()
                    # ### MODIFICATION ###: Gestion améliorée des erreurs d'existence
                    if 'already exists' in error_str or 'already taken' in error_str:
                        self.log(f"AVERTISSEMENT: Le super-utilisateur (ou son email) '{config['superuser_username']}' existe déjà. Création ignorée.", "SUCCESS")
                    else:
                        raise Exception(f"Échec de la création du super-utilisateur. Erreur:\n{e}")
            else:
                self.log("Étape 5: Création du super-utilisateur ignorée (option désactivée).", "STEP")


            # --- 6. Build Frontend ---
            self.progress['value'] = 90; self.log("Étape 6: Compilation du Frontend...", "STEP")
            self._execute('npm run build', "Build du frontend", cwd=full_frontend_path)

            self.progress['value'] = 100
            self.log("INSTALLATION DE BASE TERMINÉE AVEC SUCCÈS!", "SUCCESS")
            self.next_button.config(state="normal")
            
        except Exception as e:
            self.log(f"ERREUR FATALE: {e}", "ERROR")
            messagebox.showerror("Erreur d'installation", f"Une erreur a interrompu le processus:\n\n{e}")
            self.install_button.config(state="normal")

# =============================================================================
# Page 6: Fin
# =============================================================================
class FinishPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.title = ttk.Label(self, text="Installation Terminée !", font=("Segoe UI", 22, "bold"))
        self.title.pack(pady=20)
        ttk.Label(self, text="L'installation des fichiers et la configuration de base sont terminées.\nPour que l'application soit pleinement opérationnelle, des étapes manuelles sont **indispensables**.", font=("Segoe UI", 11)).pack(pady=10)
        next_steps_frame = ttk.LabelFrame(self, text="Prochaines Étapes Critiques", padding=15)
        next_steps_frame.pack(fill="both", expand=True, padx=40, pady=10)
        steps = ["1. Configurer les Services Windows: Utilisez NSSM ou un outil similaire pour exécuter en continu :\n   - Le serveur backend (via Gunicorn ou Uvicorn)\n   - Celery Worker et Celery Beat",
                 "2. Configurer un Reverse Proxy (Nginx recommandé): Pour servir les fichiers du frontend (dossier 'build'),\n   rediriger les appels API vers le backend, et gérer le HTTPS.",
                 "3. Vérifier les Services de Base: Assurez-vous que PostgreSQL et Redis démarrent automatiquement avec le serveur."]
        for step in steps: ttk.Label(next_steps_frame, text=step, justify="left", wraplength=700).pack(anchor="w", pady=5)
        ttk.Button(self, text="Fermer l'Assistant", command=controller.destroy).pack(pady=20)

# =============================================================================
# Point d'entrée de l'application
# =============================================================================
if __name__ == "__main__":
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            if messagebox.askyesno("Droits Administrateur Requis", "Cet assistant fonctionne mieux avec des droits administrateur.\nVoulez-vous le redémarrer en tant qu'administrateur ?"):
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit(0)
    except Exception: pass
    
    app = InstallerWizard()
    app.mainloop()
