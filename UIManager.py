import os
import fnmatch
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import ast

# Required for modern themes (light/dark mode)
import sv_ttk

import utils

class PlaceholderEntry(ttk.Entry):
    """
    A custom ttk.Entry widget that displays placeholder text.
    """
    def __init__(self, container, placeholder, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = 'grey'
        self.default_fg_color = self['foreground']

        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._add_placeholder)
        self._add_placeholder()

    def _add_placeholder(self, e=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self['foreground'] = self.placeholder_color

    def _clear_placeholder(self, e=None):
        if self.get() == self.placeholder:
            self.delete(0, 'end')
            self['foreground'] = self.default_fg_color

    def get(self):
        content = super().get()
        if content == self.placeholder:
            return ""
        return content

class UIManager:
    """
    Handles the creation, layout, and events of all UI components.
    """
    def __init__(self, app):
        self.app = app
        self.root = app
        self.tree_item_paths = {}
        self.show_ignored_separately = tk.BooleanVar(value=False)
        self.hide_ignored = tk.BooleanVar(value=False)
        self._all_tree_items_master_list = [] # A stable cache for filtering

        self.create_widgets()
        self.create_menu()
        self.set_theme(self.app.theme_var.get())
        self._update_view_options()

    def create_widgets(self):
        """Creates and arranges all the main widgets in the application window."""
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tree_container = ttk.LabelFrame(main_pane, text="File Explorer")
        main_pane.add(tree_container, weight=2)

        options_frame = ttk.Frame(tree_container)
        options_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(options_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self.search_entry = PlaceholderEntry(options_frame, "Search for files or folders...", textvariable=self.app.filter_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.app.filter_var.trace_add("write", self.filter_tree)

        self.separate_check = ttk.Checkbutton(
            options_frame,
            text="Separate Ignored",
            variable=self.show_ignored_separately,
            command=self._update_view_options
        )
        self.separate_check.pack(side=tk.LEFT, padx=(10, 0))
        
        self.hide_check = ttk.Checkbutton(
            options_frame,
            text="Hide Ignored",
            variable=self.hide_ignored,
            command=self.populate_file_tree
        )
        self.hide_check.pack(side=tk.LEFT, padx=(10, 0))

        self.tree_panes = ttk.PanedWindow(tree_container, orient=tk.VERTICAL)
        self.tree_panes.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        included_frame = ttk.Frame(self.tree_panes)
        self.tree_panes.add(included_frame, weight=3)

        self.tree = ttk.Treeview(included_frame, columns=("Status", "Size", "Type"), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="File/Folder Name")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Size", text="Size (KB)")
        self.tree.heading("Type", text="Type")
        self.tree.column("#0", width=250)
        self.tree.column("Status", width=100, anchor="center")
        self.tree.column("Size", width=80, anchor="e")
        self.tree.column("Type", width=80, anchor="w")

        tree_scrollbar = ttk.Scrollbar(included_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.ignored_frame = ttk.Frame(self.tree_panes)
        self.ignored_tree = ttk.Treeview(self.ignored_frame, columns=("Status", "Size", "Type"), show="tree headings", selectmode="extended")
        self.ignored_tree.heading("#0", text="Ignored Files & Folders")
        self.ignored_tree.heading("Status", text="Reason")
        self.ignored_tree.column("#0", width=250)
        self.ignored_tree.column("Status", width=120)
        self.ignored_tree.column("Size", width=0, stretch=tk.NO)
        self.ignored_tree.column("Type", width=0, stretch=tk.NO)

        ignored_scrollbar = ttk.Scrollbar(self.ignored_frame, orient="vertical", command=self.ignored_tree.yview)
        self.ignored_tree.configure(yscrollcommand=ignored_scrollbar.set)
        ignored_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ignored_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.tag_configure('global_ignore', foreground='gray')
        self.tree.tag_configure('session_ignore', foreground='#A9A9A9')
        self.tree_context_menu = tk.Menu(self.root, tearoff=0)
        
        self.tree.bind("<Button-3>", self.show_tree_context_menu)
        self.ignored_tree.bind("<Button-3>", self.show_tree_context_menu)

        ttk.Button(tree_container, text="Export Tree Report", command=lambda: utils.export_tree_report(self.app)).pack(pady=5, padx=5, fill=tk.X)

        settings_pane = ttk.Frame(main_pane)
        main_pane.add(settings_pane, weight=1)

        folder_group = ttk.LabelFrame(settings_pane, text="1. Select Root Folder")
        folder_group.pack(fill=tk.X, pady=(0, 10))

        self.folder_entry = ttk.Entry(folder_group, textvariable=self.app.root_folder, state="readonly")
        self.folder_entry.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=4, padx=5, pady=5)

        self.recent_menu_button = ttk.Menubutton(folder_group, text="...")
        self.recent_menu_button.pack(side=tk.LEFT, padx=(0, 5))
        self.recent_menu = tk.Menu(self.recent_menu_button, tearoff=0)
        self.recent_menu_button["menu"] = self.recent_menu
        self.populate_recent_folders_menu()

        settings_frame = ttk.LabelFrame(settings_pane, text="2. Configure Settings")
        settings_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        ttk.Label(settings_frame, text="File Extensions:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)

        file_types_frame = ttk.Frame(settings_frame)
        file_types_frame.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Entry(file_types_frame, textvariable=self.app.file_types).pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.presets_menu_button = ttk.Menubutton(file_types_frame, text="Presets")
        self.presets_menu_button.pack(side=tk.LEFT, padx=(5,0))
        self.presets_menu = tk.Menu(self.presets_menu_button, tearoff=0)
        self.presets_menu_button["menu"] = self.presets_menu
        self.populate_file_type_presets_menu()

        ttk.Label(settings_frame, text="Output Format:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        output_combobox = ttk.Combobox(settings_frame, textvariable=self.app.output_format, values=["TXT", "PDF", "DOCX", "PPTX"], state="readonly")
        output_combobox.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        output_combobox.bind("<<ComboboxSelected>>", self.suggest_extensions)

        options_frame = ttk.LabelFrame(settings_frame, text="Output Options")
        options_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Checkbutton(options_frame, text="Include File Headers", variable=self.app.include_headers).pack(side=tk.LEFT, padx=5)

        action_frame = ttk.Frame(settings_pane)
        action_frame.pack(fill=tk.X, pady=(10, 0), side=tk.BOTTOM)

        self.start_button = ttk.Button(action_frame, text="Start Consolidation", command=self.app.start_consolidation, style='Accent.TButton')
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=5)
        self.cancel_button = ttk.Button(action_frame, text="Cancel", command=self.app.request_cancel, state="disabled")
        self.cancel_button.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=5, padx=10)

        self.progress = ttk.Progressbar(settings_pane, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, pady=10, side=tk.BOTTOM)

        status_frame = ttk.Frame(settings_pane)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(status_frame, text="Ready.")
        self.status_label.pack(side=tk.LEFT)
        self.view_errors_button = ttk.Button(status_frame, text="View Errors", command=self.show_errors, state="disabled")
        self.view_errors_button.pack(side=tk.RIGHT)

        settings_frame.columnconfigure(1, weight=1)
        style = ttk.Style(self.root)
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))

    def _update_view_options(self):
        """Manages the state of view checkboxes and refreshes the tree."""
        if self.show_ignored_separately.get():
            self.hide_check.config(state="disabled")
            self.hide_ignored.set(False)
        else:
            self.hide_check.config(state="normal")
        self.populate_file_tree()

    def create_menu(self):
        """Creates the main application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        self.profile_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Profiles", menu=self.profile_menu)
        self.profile_menu.add_command(label="Save Current as Profile...", command=self.app.config_handler.save_profile)
        self.profile_menu.add_separator()
        self.populate_profiles_menu()

        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Edit Global Ignores...", command=self.open_global_ignore_editor)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        theme_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        theme_menu.add_radiobutton(label="Light", variable=self.app.theme_var, value="light", command=lambda: self.set_theme("light"))
        theme_menu.add_radiobutton(label="Dark", variable=self.app.theme_var, value="dark", command=lambda: self.set_theme("dark"))

    def set_theme(self, theme_name):
        """Sets the application theme using sv_ttk."""
        sv_ttk.set_theme(theme_name)
        self.app.theme_var.set(theme_name)

    def populate_profiles_menu(self):
        """Loads profile names into the 'Profiles' menu."""
        last_index = self.profile_menu.index("end")
        if last_index and last_index >= 2: self.profile_menu.delete(2, last_index)
        if not self.app.profiles:
            self.profile_menu.add_command(label="No profiles saved", state="disabled")
        else:
            for name in self.app.profiles:
                self.profile_menu.add_command(label=f"Load '{name}'", command=lambda n=name: self.app.config_handler.load_profile(n))

    def populate_recent_folders_menu(self):
        """Loads recent folder paths into the recent folders menu."""
        self.recent_menu.delete(0, tk.END)
        self.recent_menu.add_command(label="Browse...", command=self.select_root_folder)
        self.recent_menu.add_separator()
        if not self.app.recent_folders:
            self.recent_menu.add_command(label="No recent folders", state="disabled")
        else:
            for folder in self.app.recent_folders:
                self.recent_menu.add_command(label=folder, command=lambda f=folder: self.set_root_folder(f, update_recent=False))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear Recent", command=self.clear_recent_folders)

    def populate_file_type_presets_menu(self):
        """Populates the file type presets dropdown menu."""
        self.presets_menu.delete(0, tk.END)
        presets = {
            "Code Project": ".py,.js,.html,.css,.json,.xml,.md,.txt",
            "Documents": ".docx,.pdf,.txt",
            "All Text Files": ".txt,.md,.csv,.log,.xml,.json",
            "Microsoft Office": ".docx,.pptx,.xlsx"
        }
        for name, extensions in presets.items():
            self.presets_menu.add_command(label=name, command=lambda ex=extensions: self.set_file_types_from_preset(ex))

    def set_file_types_from_preset(self, preset_string):
        """Sets the file types entry from a chosen preset."""
        self.app.file_types.set(preset_string)
        self.populate_file_tree()

    def clear_recent_folders(self):
        """Clears the list of recent folders."""
        self.app.recent_folders.clear()
        self.populate_recent_folders_menu()

    def handle_drop(self, event):
        """Handles a drag-and-drop event to set the root folder."""
        paths = self.root.tk.splitlist(event.data)
        for path in paths:
            if os.path.isdir(path):
                self.set_root_folder(path, update_recent=True)
                return
        messagebox.showwarning("Invalid Drop", "Could not find a valid folder in the dropped items.")

    def set_root_folder(self, folder_path, update_recent=True):
        """Sets the root folder, updates the file tree, and manages the recent folders list."""
        self.app.root_folder.set(folder_path)
        self.populate_file_tree()
        if update_recent:
            if folder_path in self.app.recent_folders:
                self.app.recent_folders.remove(folder_path)
            self.app.recent_folders.insert(0, folder_path)
            self.app.recent_folders = self.app.recent_folders[:self.app.config_handler.MAX_RECENT_FOLDERS]
            self.populate_recent_folders_menu()

    def select_root_folder(self):
        """Opens a dialog to select the root folder."""
        folder = tk.filedialog.askdirectory(title="Select Root Folder")
        if folder: self.set_root_folder(folder, update_recent=True)

    def populate_file_tree(self):
        """Scans the file system and populates the tree(s) based on view settings."""
        for tree in [self.tree, self.ignored_tree]:
            tree.delete(*tree.get_children())
        self.tree_item_paths.clear()
        self._all_tree_items_master_list = []

        if self.show_ignored_separately.get():
            try: self.tree_panes.add(self.ignored_frame, weight=1)
            except tk.TclError: pass
        else:
            try: self.tree_panes.forget(self.ignored_frame)
            except tk.TclError: pass

        root_path = self.app.root_folder.get()
        if not root_path or not os.path.isdir(root_path): return

        try:
            session_folder_ignores = ast.literal_eval(self.app.folder_ignore_patterns.get())
            session_file_ignores = ast.literal_eval(self.app.file_ignore_patterns.get())
        except (ValueError, SyntaxError):
            session_folder_ignores, session_file_ignores = [], []
            messagebox.showwarning("Invalid Patterns", "Ignore patterns were invalid and reset to defaults.")

        extensions = [ext.strip().lower() for ext in self.app.file_types.get().split(',') if ext.strip()]
        path_to_node_map = {}

        # Add root node to the main tree and map
        root_node_id = self.tree.insert("", "end", text=os.path.basename(root_path), open=True, values=("", "", "Folder"))
        path_to_node_map[root_path] = root_node_id
        self.tree_item_paths[root_node_id] = root_path

        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            try:
                # Prune directories from traversal based on all ignore patterns
                dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in session_folder_ignores) and 
                            not any(fnmatch.fnmatch(d, pat) for pat in self.app.config_handler.global_folder_ignores)]

                parent_node_id = path_to_node_map.get(dirpath, "")

                for d in dirnames:
                    full_path = os.path.join(dirpath, d)
                    node_id = self.tree.insert(parent_node_id, 'end', text=d, values=("", "", "Folder"))
                    path_to_node_map[full_path] = node_id
                    self.tree_item_paths[node_id] = full_path

                for f in filenames:
                    full_path = os.path.join(dirpath, f)
                    basename = f

                    is_ext_match = any(basename.lower().endswith(ext) for ext in extensions)
                    is_global_file_ignored = any(fnmatch.fnmatch(basename, pat) for pat in self.app.config_handler.global_file_ignores)
                    is_session_file_ignored = any(fnmatch.fnmatch(basename, pat) for pat in session_file_ignores)
                    is_ignored = is_global_file_ignored or is_session_file_ignored or not is_ext_match

                    if self.hide_ignored.get() and is_ignored and not self.show_ignored_separately.get():
                        continue

                    status, tags = "Included", ()
                    if is_session_file_ignored: status, tags = "Ignored (Session)", ('session_ignore',)
                    elif is_global_file_ignored: status, tags = "Ignored (Global)", ('global_ignore',)
                    elif not is_ext_match: status, tags = "Ignored (Type)", ('type_ignore',)

                    try: size_kb = f"{os.path.getsize(full_path) / 1024:.2f}"
                    except OSError: size_kb = "N/A"

                    file_ext = os.path.splitext(basename)[1]

                    tree_to_use = self.ignored_tree if is_ignored and self.show_ignored_separately.get() else self.tree
                    parent_id = path_to_node_map.get(dirpath, "")

                    if self.show_ignored_separately.get() and is_ignored:
                        if dirpath not in path_to_node_map:
                            path_to_node_map[dirpath] = self.ignored_tree.insert("", 'end', text=os.path.basename(dirpath), open=True, values=("", "", "Folder"))
                        parent_id = path_to_node_map[dirpath]

                    node_id = tree_to_use.insert(parent_id, 'end', text=basename, tags=tags, values=(status, size_kb, file_ext))
                    self.tree_item_paths[node_id] = full_path
                    if not is_ignored:  # Only cache non-ignored items for filtering
                        self._all_tree_items_master_list.append(node_id)
            except PermissionError as e:
                self.app.processing_errors.append(f"Permission denied for {dirpath}: {e}")

        self.filter_tree()

    def filter_tree(self):
        """Filters the tree based on the search entry text."""
        search_text = self.app.filter_var.get().lower()
        self.tree.delete(*self.tree.get_children())  # Clear current view
        for node_id in self._all_tree_items_master_list:
            if node_id in self.tree_item_paths:
                path = self.tree_item_paths[node_id].lower()
                if search_text in path or search_text in self.tree.item(node_id, "text").lower():
                    # Rebuild visible hierarchy
                    parent_path = os.path.dirname(path)
                    while parent_path and parent_path != self.app.root_folder.get():
                        if parent_path not in self.tree_item_paths.values():
                            parent_id = self.tree.insert("", "end", text=os.path.basename(parent_path), values=("", "", "Folder"))
                            self.tree_item_paths[parent_id] = parent_path
                        parent_path = os.path.dirname(parent_path)
                    parent_id = next((k for k, v in self.tree_item_paths.items() if v == os.path.dirname(path)), "")
                    self.tree.insert(parent_id, "end", iid=node_id, **self.tree.item(node_id, "values"))




    def show_tree_context_menu(self, event):
        """Displays a context menu for items in the file tree."""
        tree_widget = event.widget
        selected_ids = tree_widget.selection()
        if not selected_ids: return
        
        self.tree_context_menu.delete(0, tk.END)
        
        item_id = selected_ids[0]
        values = tree_widget.item(item_id, "values")
        is_folder = values and values[2] == "Folder"

        if tree_widget is self.ignored_tree:
            self.tree_context_menu.add_command(label="Unignore Selected", command=self.unignore_selected)
        else:
            tags = tree_widget.item(item_id, "tags")
            if 'session_ignore' in tags or 'global_ignore' in tags:
                self.tree_context_menu.add_command(label="Unignore Selected", command=self.unignore_selected)
            else:
                self.tree_context_menu.add_command(label="Ignore Selected", command=self.ignore_selected)

        self.tree_context_menu.add_separator()
        self.tree_context_menu.add_command(label="Open", command=self.open_selected_file, state="normal" if len(selected_ids) == 1 else "disabled")
        self.tree_context_menu.add_command(label="Refresh Tree", command=self.populate_file_tree)
        self.tree_context_menu.tk_popup(event.x_root, event.y_root)

    def ignore_selected(self):
        """Adds the selected tree items to the session ignore list."""
        selected_ids = self.tree.selection()
        if not selected_ids: return

        folder_patterns_list = eval(self.app.folder_ignore_patterns.get())
        file_patterns_list = eval(self.app.file_ignore_patterns.get())

        for item_id in selected_ids:
            item_text = self.tree.item(item_id, "text")
            is_folder = self.tree.item(item_id, "values")[2] == "Folder"
            
            if is_folder:
                if item_text not in folder_patterns_list: folder_patterns_list.append(item_text)
            else:
                if item_text not in file_patterns_list: file_patterns_list.append(item_text)
        
        self.app.folder_ignore_patterns.set(str(folder_patterns_list))
        self.app.file_ignore_patterns.set(str(file_patterns_list))
        self.populate_file_tree()

    def unignore_selected(self):
        """Removes the selected tree items from the session ignore list."""
        selected_ids = self.tree.selection() or self.ignored_tree.selection()
        tree_widget = self.tree if self.tree.selection() else self.ignored_tree
        if not selected_ids: return

        folder_patterns_list = eval(self.app.folder_ignore_patterns.get())
        file_patterns_list = eval(self.app.file_ignore_patterns.get())

        for item_id in selected_ids:
            item_text = tree_widget.item(item_id, "text")
            is_folder = tree_widget.item(item_id, "values")[2] == "Folder"
            
            if is_folder:
                if item_text in folder_patterns_list: folder_patterns_list.remove(item_text)
            else:
                if item_text in file_patterns_list: file_patterns_list.remove(item_text)
        
        self.app.folder_ignore_patterns.set(str(folder_patterns_list))
        self.app.file_ignore_patterns.set(str(file_patterns_list))
        self.populate_file_tree()

    def open_selected_file(self):
        """Opens the selected file or folder using the OS's default application."""
        selected_ids = self.tree.selection() or self.ignored_tree.selection()
        if not selected_ids: return
        
        item_id = selected_ids[0]
        full_path = self.tree_item_paths.get(item_id)
        
        if not full_path or not os.path.exists(full_path):
            messagebox.showerror("Error", f"Path not found: {full_path}")
            return
        
        try:
            os.startfile(full_path)
        except AttributeError:
            try: subprocess.call(['open', full_path])
            except:
                try: subprocess.call(['xdg-open', full_path])
                except: messagebox.showerror("Error", "Could not open file automatically.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def show_errors(self):
        """Displays a window with all processing errors."""
        if not self.app.processing_errors: return
        utils.show_error_log(self.root, self.app.processing_errors)

    def reset_ui_state(self):
        """Resets the UI to its default state after an operation."""
        self.progress["value"] = 0
        self.start_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.app.cancel_requested = False
        if "cancelled" not in self.status_label.cget('text') and "request" not in self.status_label.cget('text'):
            self.status_label.config(text="Ready.")

    def open_global_ignore_editor(self):
        """Opens the editor for global ignore patterns."""
        GlobalIgnoreEditor(self.root, self.app)
    
    def suggest_extensions(self, event):
        """Suggests appropriate file extensions when the output format changes."""
        output_format = self.app.output_format.get()
        is_office_installed = self.app.file_processor.OFFICE_INSTALLED
        suggestions = {
            "TXT": ".txt,.py,.md,.json,.xml,.html,.css,.js",
            "PDF": ".pdf,.docx,.pptx" if is_office_installed else ".pdf",
            "DOCX": ".docx",
            "PPTX": ".pptx"
        }.get(output_format, "")
        if suggestions and self.app.file_types.get() != suggestions:
            if messagebox.askyesno("Suggestion", f"Would you like to set file extensions to the recommended types for {output_format} output?\n\n({suggestions})"):
                self.app.file_types.set(suggestions)
                self.populate_file_tree()

class GlobalIgnoreEditor(tk.Toplevel):
    """A Toplevel window for editing global ignore patterns."""
    def __init__(self, parent, app):
        super().__init__(parent)
        self.parent = parent
        self.app = app
        self.title("Edit Global Ignore Patterns")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)

        pane = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        pane.grid(row=0, column=0, columnspan=2, sticky="nsew")

        self.listbox_map = {}
        folder_frame = self.create_listbox_frame(pane, "Global Folder Ignores")
        self.folder_listbox = self.listbox_map["Global Folder Ignores"]
        pane.add(folder_frame, weight=1)

        file_frame = self.create_listbox_frame(pane, "Global File Ignores")
        self.file_listbox = self.listbox_map["Global File Ignores"]
        pane.add(file_frame, weight=1)

        for item in self.app.config_handler.global_folder_ignores: self.folder_listbox.insert(tk.END, item)
        for item in self.app.config_handler.global_file_ignores: self.file_listbox.insert(tk.END, item)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=(10, 0), sticky="e")
        ttk.Button(btn_frame, text="Save & Close", command=self.save_and_close, style="Accent.TButton").pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=10)

    def create_listbox_frame(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=5)
        list_area = ttk.Frame(frame)
        list_area.pack(fill=tk.BOTH, expand=True, pady=5)
        listbox = tk.Listbox(list_area, height=10, selectmode="extended")
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox_map[title] = listbox
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="Add", command=lambda: self.add_item(listbox)).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Remove", command=lambda: self.remove_item(listbox)).pack(side=tk.LEFT, padx=5)
        return frame

    def add_item(self, listbox):
        item = simpledialog.askstring("Add Pattern", "Enter new ignore pattern:", parent=self)
        if item: listbox.insert(tk.END, item)

    def remove_item(self, listbox):
        selected = listbox.curselection()
        if not selected: return
        for i in reversed(selected): listbox.delete(i)

    def save_and_close(self):
        self.app.config_handler.global_folder_ignores = list(self.folder_listbox.get(0, tk.END))
        self.app.config_handler.global_file_ignores = list(self.file_listbox.get(0, tk.END))
        self.app.config_handler.save_settings()
        self.app.ui_manager.populate_file_tree()
        self.destroy()
