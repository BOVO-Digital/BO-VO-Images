# install_prereqs_gui.py
# Version 2.0 - Ne force plus la réinstallation des prérequis.
# - Supprime le flag --force de Chocolatey pour ignorer ou mettre à jour les paquets existants.
# - Améliore le feedback utilisateur sur le comportement de l'installation.

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import os
import sys
import shutil
import ctypes
import queue
from datetime import datetime

# =============================================================================
# Classe pour exécuter les commandes et logger la sortie
# =============================================================================
class CommandRunner:
    def __init__(self, command, log_widget, on_complete=None):
        self.command = command
        self.log_widget = log_widget
        self.on_complete = on_complete
        self.output_queue = queue.Queue()
        self.process = None

    def log(self, message, level="INFO"):
        self.log_widget.config(state="normal")
        now = datetime.now().strftime("%H:%M:%S")
        tag = level if level in ["SUCCESS", "ERROR", "CMD"] else "INFO"
        self.log_widget.insert(tk.END, f"[{now}] {message}\n", tag)
        self.log_widget.config(state="disabled")
        self.log_widget.see(tk.END)
        self.log_widget.update_idletasks()

    def _reader_thread(self):
        try:
            for line in iter(self.process.stdout.readline, ''):
                self.output_queue.put(line)
            self.process.stdout.close()
            self.process.wait()
        except Exception:
            pass # Silencieux, car on gère les erreurs via le returncode
        finally:
            self.output_queue.put(None) # Sentinel pour indiquer la fin

    def run(self):
        self.log(f"Exécution de la commande :\n{self.command}", "CMD")
        try:
            self.process = subprocess.Popen(
                ['powershell.exe', '-NoProfile', '-Command', self.command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            thread = threading.Thread(target=self._reader_thread, daemon=True)
            thread.start()
            
            self._poll_queue()

        except FileNotFoundError:
            self.log("Erreur : 'powershell.exe' introuvable. Assurez-vous que PowerShell est installé et dans le PATH.", "ERROR")
            if self.on_complete: self.on_complete(False)
        except Exception as e:
            self.log(f"Erreur inattendue au lancement du processus : {e}", "ERROR")
            if self.on_complete: self.on_complete(False)
    
    def _poll_queue(self):
        try:
            line = self.output_queue.get_nowait()
            if line is None: # Fin du stream
                if self.process.returncode == 0:
                    self.log("Commande terminée avec succès.", "SUCCESS")
                    if self.on_complete: self.on_complete(True)
                else:
                    self.log(f"La commande a échoué avec le code d'erreur : {self.process.returncode}", "ERROR")
                    if self.on_complete: self.on_complete(False)
                return
            else:
                if line.strip():
                    self.log_widget.config(state="normal")
                    self.log_widget.insert(tk.END, line)
                    self.log_widget.config(state="disabled")
                    self.log_widget.see(tk.END)
        except queue.Empty:
            pass
        
        self.log_widget.after(100, self._poll_queue)


# =============================================================================
# Classe principale du Wizard
# =============================================================================
class PrereqWizard(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Assistant d'Installation des Prérequis")
        self.geometry("900x700")

        self.style = ttk.Style(self)
        self.style.configure("TButton", padding=6, relief="flat", font=('Segoe UI', 10))

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        self.frames = {}
        for F in (WelcomePage, ChocoCheckPage, ToolsInstallPage, PostgresPage, FinishPage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(WelcomePage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()

# =============================================================================
# Classe de base pour les pages
# =============================================================================
class WizardPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

    def create_log_area(self):
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_text = tk.Text(log_frame, wrap="word", state="disabled", font=("Consolas", 9), relief=tk.SOLID, borderwidth=1)
        
        v_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.config(yscrollcommand=v_scroll.set)
        
        v_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.log_text.tag_configure("SUCCESS", foreground="#008000", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("ERROR", foreground="#d91e18")
        self.log_text.tag_configure("CMD", foreground="#000080", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("INFO", foreground="#555555")
        return self.log_text

# =============================================================================
# Page 1: Accueil
# =============================================================================
class WelcomePage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ttk.Label(self, text="Installation des Prérequis", font=("Segoe UI", 22, "bold")).pack(pady=20)
        info = ("Cet assistant va installer les composants nécessaires pour l'application RH.\n\n"
                "Il utilise l'outil Chocolatey pour automatiser les installations.\n"
                "  • Il installera Chocolatey si celui-ci est absent.\n"
                "  • Il installera Git, Python, Node.js et VS Code.\n"
                "  • Il installera et configurera une base de données PostgreSQL.\n\n"
                "Une connexion Internet est requise.\n"
                "Ce processus doit être exécuté avec des droits d'administrateur.")
        ttk.Label(self, text=info, justify="left", font=("Segoe UI", 11)).pack(pady=20, padx=40)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        ttk.Button(btn_frame, text="Suivant", command=lambda: controller.show_frame(ChocoCheckPage)).pack(side="right")

# =============================================================================
# Page 2: Vérification et Installation de Chocolatey
# =============================================================================
class ChocoCheckPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ttk.Label(self, text="Étape 1: Vérification de Chocolatey", font=("Segoe UI", 16, "bold")).pack(pady=10)
        self.status_label = ttk.Label(self, text="Vérification en cours...", font=("Segoe UI", 12))
        self.status_label.pack(pady=10)
        
        self.log_text = self.create_log_area()

        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        self.install_button = ttk.Button(self.btn_frame, text="Installer Chocolatey", command=self.install_choco, state="disabled")
        self.install_button.pack(side="left")
        self.next_button = ttk.Button(self.btn_frame, text="Suivant", command=lambda: controller.show_frame(ToolsInstallPage), state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(self.btn_frame, text="Précédent", command=lambda: controller.show_frame(WelcomePage)).pack(side="right", padx=10)

    def on_show(self):
        self.check_choco()

    def check_choco(self):
        if shutil.which("choco"):
            self.status_label.config(text="Chocolatey est déjà installé.", foreground="green")
            self.install_button.config(state="disabled")
            self.next_button.config(state="normal")
            self.log_text.config(state="normal")
            self.log_text.delete('1.0', tk.END)
            self.log_text.insert('1.0', "Chocolatey détecté. Vous pouvez passer à l'étape suivante.")
            self.log_text.config(state="disabled")
        else:
            self.status_label.config(text="Chocolatey n'est pas installé.", foreground="red")
            self.install_button.config(state="normal")
            self.next_button.config(state="disabled")

    def install_choco(self):
        self.install_button.config(state="disabled")
        self.next_button.config(state="disabled")
        command = (
            "Set-ExecutionPolicy Bypass -Scope Process -Force; "
            "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
        )
        runner = CommandRunner(command, self.log_text, on_complete=self.on_choco_install_complete)
        runner.run()

    def on_choco_install_complete(self, success):
        if success:
            messagebox.showinfo("Succès", "Chocolatey a été installé. Vous devez redémarrer ce terminal ou cet assistant pour que le PATH soit mis à jour.\n\nL'assistant va maintenant se fermer. Veuillez le relancer.")
            self.controller.destroy()
        else:
            messagebox.showerror("Erreur", "L'installation de Chocolatey a échoué. Veuillez consulter les logs.")
            self.install_button.config(state="normal")

# =============================================================================
# Page 3: Installation des outils de dev
# =============================================================================
class ToolsInstallPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ttk.Label(self, text="Étape 2: Installer les Outils de Développement", font=("Segoe UI", 16, "bold")).pack(pady=10)
        
        ### AJOUT ###: Label d'information sur le comportement de l'installation.
        info_label = ttk.Label(self, text="Cochez les outils à installer. Si un outil est déjà présent, il sera mis à jour ou ignoré.", font=("Segoe UI", 10))
        info_label.pack(pady=(0, 10))

        self.tools = {
            "git": {"var": tk.BooleanVar(value=True), "cmd": "git"},
            "python": {"var": tk.BooleanVar(value=True), "cmd": "python"},
            "nodejs-lts": {"var": tk.BooleanVar(value=True), "cmd": "nodejs-lts"},
            "vscode": {"var": tk.BooleanVar(value=True), "cmd": "vscode"}
        }

        check_frame = ttk.Frame(self)
        check_frame.pack(pady=5, padx=20, fill="x")
        for name, data in self.tools.items():
            ttk.Checkbutton(check_frame, text=f"Installer {name}", variable=data["var"]).pack(anchor="w")

        self.log_text = self.create_log_area()

        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        self.install_button = ttk.Button(self.btn_frame, text="Lancer l'Installation", command=self.run_installation)
        self.install_button.pack(side="left")
        self.next_button = ttk.Button(self.btn_frame, text="Suivant", command=lambda: controller.show_frame(PostgresPage), state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(self.btn_frame, text="Précédent", command=lambda: controller.show_frame(ChocoCheckPage)).pack(side="right", padx=10)
        
        self.install_queue = []

    def run_installation(self):
        self.install_button.config(state="disabled")
        self.next_button.config(state="disabled")
        
        self.install_queue = [data['cmd'] for name, data in self.tools.items() if data['var'].get()]
        if not self.install_queue:
            messagebox.showinfo("Information", "Aucun outil sélectionné. Passage à l'étape suivante.")
            self.next_button.config(state="normal")
            self.install_button.config(state="normal")
            return
            
        self.process_next_in_queue()

    def process_next_in_queue(self):
        if not self.install_queue:
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, "\n=== TOUTES LES INSTALLATIONS SONT TERMINÉES ===\n", "SUCCESS")
            self.log_text.config(state="disabled")
            self.next_button.config(state="normal")
            self.install_button.config(state="normal")
            return

        tool = self.install_queue.pop(0)
        
        ### MODIFICATION ###: Le flag --force a été retiré.
        command = f"choco install {tool} -y"
        
        runner = CommandRunner(command, self.log_text, on_complete=self.on_tool_install_complete)
        runner.run()

    def on_tool_install_complete(self, success):
        if not success:
            messagebox.showwarning("Erreur d'installation", "L'installation d'un outil a échoué. Vérifiez les logs. Vous pouvez continuer, mais l'application risque de ne pas fonctionner.")
        # On continue même en cas d'échec pour essayer d'installer les autres outils.
        self.process_next_in_queue()

# =============================================================================
# Page 4: Configuration de PostgreSQL
# =============================================================================
class PostgresPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        self.controller = controller
        ttk.Label(self, text="Étape 3: Installation de PostgreSQL", font=("Segoe UI", 16, "bold")).pack(pady=10)

        form_frame = ttk.LabelFrame(self, text="Paramètres de la base de données", padding=15)
        form_frame.pack(padx=20, pady=10, fill="x")
        
        self.pg_vars = {
            "admin_pass": tk.StringVar(),
            "db_name": tk.StringVar(value="rh_app_db"),
            "db_user": tk.StringVar(value="rh_app_user"),
            "db_pass": tk.StringVar()
        }

        ttk.Label(form_frame, text="Mot de passe pour l'utilisateur 'postgres' (admin):").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.pg_vars["admin_pass"], show="*").grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Separator(form_frame, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        
        ttk.Label(form_frame, text="Nom de la nouvelle base de données:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.pg_vars["db_name"]).grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form_frame, text="Nom du nouvel utilisateur de la base:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.pg_vars["db_user"]).grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(form_frame, text="Mot de passe du nouvel utilisateur:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(form_frame, textvariable=self.pg_vars["db_pass"], show="*").grid(row=4, column=1, sticky="ew", pady=5, padx=5)
        
        form_frame.columnconfigure(1, weight=1)

        self.log_text = self.create_log_area()

        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        self.install_button = ttk.Button(self.btn_frame, text="Installer et Configurer PostgreSQL", command=self.run_postgres_setup)
        self.install_button.pack(side="left")
        self.next_button = ttk.Button(self.btn_frame, text="Terminer", command=lambda: controller.show_frame(FinishPage), state="disabled")
        self.next_button.pack(side="right")
        ttk.Button(self.btn_frame, text="Précédent", command=lambda: controller.show_frame(ToolsInstallPage)).pack(side="right", padx=10)

    def run_postgres_setup(self):
        admin_pass = self.pg_vars["admin_pass"].get()
        if not admin_pass:
            messagebox.showerror("Erreur", "Le mot de passe administrateur ('postgres') est obligatoire.")
            return

        self.install_button.config(state="disabled")
        self.next_button.config(state="disabled")

        self.controller.db_details = {k: v.get() for k, v in self.pg_vars.items()}

        # La commande Choco pour Postgres n'utilise le mot de passe que lors de la première installation.
        # Sur les exécutions suivantes, elle sera ignorée, ce qui est le comportement souhaité.
        command = f"choco install postgresql14 --params '\"/Password:{admin_pass}\"' -y"
        runner = CommandRunner(command, self.log_text, on_complete=self.on_postgres_install_complete)
        runner.run()
        
    def on_postgres_install_complete(self, success):
        if not success:
            messagebox.showerror("Erreur", "L'installation de PostgreSQL a échoué. Consultez les logs.")
            self.install_button.config(state="normal")
            return
        
        self.configure_db()

    def configure_db(self):
        details = self.controller.db_details
        db_name = details['db_name']
        db_user = details['db_user']
        db_pass = details['db_pass'].replace("'", "''")

        sql_commands = [
            f"CREATE DATABASE {db_name};",
            f"CREATE USER {db_user} WITH PASSWORD '{db_pass}';",
            f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};"
        ]
        
        ps_command_block = "; ".join([f"psql -U postgres -c \\\"{cmd}\\\"" for cmd in sql_commands])
        full_command = f"$env:PGPASSWORD='{details['admin_pass']}'; {ps_command_block}"
        
        runner = CommandRunner(full_command, self.log_text, on_complete=self.on_db_config_complete)
        runner.run()

    def on_db_config_complete(self, success):
        if success:
            messagebox.showinfo("Succès", "PostgreSQL a été installé et la base de données a été configurée avec succès.")
            self.next_button.config(state="normal")
        else:
            # Ce message est important car il gère le cas où l'utilisateur relance le script
            messagebox.showerror("Erreur", "La configuration de la base de données a échoué. Il est possible que la base ou l'utilisateur existe déjà. Vérifiez les logs.")
            self.install_button.config(state="normal")

# =============================================================================
# Page 5: Fin
# =============================================================================
class FinishPage(WizardPage):
    def __init__(self, parent, controller):
        super().__init__(parent, controller)
        ttk.Label(self, text="Installation des prérequis terminée !", font=("Segoe UI", 22, "bold")).pack(pady=20)
        
        self.info_label = ttk.Label(self, justify="left", font=("Segoe UI", 11))
        self.info_label.pack(pady=10, padx=20)
        
        ttk.Label(self, text="Vous pouvez maintenant lancer l'installateur principal de l'application.", font=("Segoe UI", 11, "bold")).pack(pady=20)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        ttk.Button(btn_frame, text="Fermer", command=controller.destroy).pack(side="right")

    def on_show(self):
        details = getattr(self.controller, "db_details", {})
        if details:
            info_text = (
                "L'installation et la configuration sont terminées.\n\n"
                "Veuillez noter précieusement les informations suivantes pour les utiliser dans l'installateur de l'application :\n\n"
                f"  • Hôte de la base de données : localhost\n"
                f"  • Port PostgreSQL : 5432 (défaut)\n"
                f"  • Nom de la base de données : {details.get('db_name', 'N/A')}\n"
                f"  • Utilisateur de la base de données : {details.get('db_user', 'N/A')}\n"
                f"  • Mot de passe de l'utilisateur : {details.get('db_pass', 'N/A')}\n\n"
            )
            self.info_label.config(text=info_text)
        else:
            self.info_label.config(text="L'installation des outils est terminée.\nL'étape PostgreSQL a été ignorée ou a échoué avant la saisie des détails.")


# =============================================================================
# Point d'entrée
# =============================================================================
if __name__ == "__main__":
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if not is_admin:
        if messagebox.askyesno("Droits Administrateur Requis", 
                               "Ce programme nécessite des droits d'administrateur pour installer des logiciels via Chocolatey.\n\n"
                               "Voulez-vous le redémarrer en tant qu'administrateur ?"):
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de redémarrer en mode administrateur:\n{e}")
        sys.exit(0)
    
    app = PrereqWizard()
    app.mainloop()
