import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, filedialog

# Required for drag-and-drop
from tkinterdnd2 import DND_FILES, TkinterDnD

from UIManager import UIManager
from FileProcessor import FileProcessor
from ConfigManager import ConfigHandler
import utils

# Use TkinterDnD.Tk to enable drag-and-drop
class FileConsolidatorApp(TkinterDnD.Tk):
    """
    The main application class. It initializes the application, manages state,
    and orchestrates communication between the UI, file processing, and
    configuration handling modules.
    """
    def __init__(self):
        super().__init__()
        self.title("File Consolidator Pro")
        self.geometry("800x750")
        self.minsize(700, 600)

        # --- State Variables ---
        self.cancel_requested = False
        self.profiles = {}
        self.recent_folders = []
        self.processing_errors = []
        self.processing_queue = queue.Queue()

        # --- UI Variables (managed by the main app class) ---
        self.root_folder = tk.StringVar()
        self.file_types = tk.StringVar(value=".py,.txt,.md")
        self.output_format = tk.StringVar(value="TXT")
        self.theme_var = tk.StringVar(value="light")
        self.include_headers = tk.BooleanVar(value=True)
        self.filter_var = tk.StringVar()
        self.folder_ignore_patterns = tk.StringVar()
        self.file_ignore_patterns = tk.StringVar()

        # --- Module Instances ---
        self.config_handler = ConfigHandler(self)
        self.file_processor = FileProcessor(self)
        self.ui_manager = UIManager(self) # Must be last to build UI

        # --- Final Setup ---
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.ui_manager.handle_drop)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_queue()

        if not self.file_processor.OFFICE_INSTALLED:
            self.ui_manager.status_label.config(text="Warning: MS Office not detected (PDF conversion for DOCX/PPTX disabled).")

    def start_consolidation(self):
        """
        Gathers file paths from the UI and starts the file processing thread.
        """
        root_dir = self.root_folder.get()
        if not root_dir:
            messagebox.showerror("Error", "Please select a root folder.")
            return

        files_to_process = []
        self._collect_included_files(self.ui_manager.tree.get_children(""), files_to_process)

        if not files_to_process:
            messagebox.showinfo("No Files To Process", "No files are marked as 'Included' based on current settings.")
            return

        output_format = self.output_format.get()
        if output_format in ["DOCX", "PPTX"]:
            incompatible_found = False
            if output_format == "DOCX" and any(not f.lower().endswith('.docx') for f in files_to_process):
                incompatible_found = True
            elif output_format == "PPTX" and any(not f.lower().endswith('.pptx') for f in files_to_process):
                incompatible_found = True

            if incompatible_found and not messagebox.askyesno(
                "Incompatible Files Warning",
                f"The output format '{output_format}' only supports its own file type. Other file types will be skipped. Continue?"
            ):
                return

        file_dialog_options = {
            "TXT": ("Text", "*.txt"),
            "PDF": ("PDF", "*.pdf"),
            "DOCX": ("Word", "*.docx"),
            "PPTX": ("PowerPoint", "*.pptx")
        }
        file_type_info = file_dialog_options.get(output_format)
        output_filename = filedialog.asksaveasfilename(
            title=f"Save Consolidated {output_format} As",
            defaultextension=f".{file_type_info[1].split('.')[-1]}",
            filetypes=[(f"{file_type_info[0]} Documents", file_type_info[1]), ("All Files", "*.*")]
        )

        if not output_filename:
            self.ui_manager.status_label.config(text="Cancelled.")
            return

        self.ui_manager.start_button.config(state="disabled")
        self.ui_manager.cancel_button.config(state="normal")
        self.ui_manager.view_errors_button.config(state="disabled")
        self.cancel_requested = False
        self.processing_errors.clear()

        thread = threading.Thread(
            target=self.file_processor.process_files,
            args=(files_to_process, output_filename, output_format),
            daemon=True
        )
        thread.start()

    def _collect_included_files(self, parent_ids, file_list):
        """
        Recursively traverses the Treeview to find all files marked 'Included'.
        """
        tree = self.ui_manager.tree
        for child_id in parent_ids:
            if not tree.exists(child_id): continue
            values = tree.item(child_id, "values")
            if values and values[0] == "Included" and values[2] != "Folder":
                path_parts = [tree.item(child_id, "text")]
                parent = tree.parent(child_id)
                while parent:
                    path_parts.insert(0, tree.item(parent, "text"))
                    parent = tree.parent(parent)
                full_path = os.path.join(self.root_folder.get(), *path_parts)
                file_list.append(full_path)
            elif values and values[2] == "Folder":
                self._collect_included_files(tree.get_children(child_id), file_list)

    def check_queue(self):
        """
        Periodically checks the processing queue for messages from the worker thread
        and updates the UI accordingly.
        """
        try:
            while True:
                msg, value = self.processing_queue.get_nowait()
                if msg == "status":
                    self.ui_manager.status_label.config(text=value)
                elif msg == "progress":
                    self.ui_manager.progress["value"] = value
                elif msg == "max_progress":
                    self.ui_manager.progress["maximum"] = value
                elif msg == "done":
                    self.ui_manager.reset_ui_state()
                    if self.processing_errors:
                        self.ui_manager.view_errors_button.config(state="normal")
                        utils.show_completion_message(self, len(value[0]), len(self.processing_errors), value[-1])
                    else:
                        utils.show_completion_message(self, len(value), 0, value[-1])


        except queue.Empty:
            pass
        self.after(100, self.check_queue)

    def request_cancel(self):
        """
        Sets a flag to signal the worker thread to stop processing.
        """
        if messagebox.askyesno("Cancel?", "Are you sure you want to cancel the operation?"):
            self.cancel_requested = True
            self.ui_manager.status_label.config(text="Cancellation requested...")

    def on_closing(self):
        """
        Saves settings before the application window is closed.
        """
        self.config_handler.save_settings()
        self.destroy()

if __name__ == '__main__':
    app = FileConsolidatorApp()
    app.mainloop()
