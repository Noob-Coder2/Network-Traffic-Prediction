import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def export_tree_report(app):
    """
    Exports the current state of the file tree view to a text file.
    """
    root_path = app.root_folder.get()
    if not root_path:
        messagebox.showwarning("No Folder Selected", "Please select a root folder before exporting a report.")
        return
        
    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt")],
        title="Export Tree Report"
    )
    if not file_path: return
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"File Tree Report for: {root_path}\n")
            f.write("="*40 + "\n")
            _write_tree_node_to_file(f, app.ui_manager.tree, "", "")
        
        messagebox.showinfo("Export Successful", f"Tree report saved to {file_path}")
    except IOError as e:
        messagebox.showerror("Export Error", f"Failed to save report: {e}")

def _write_tree_node_to_file(file_handle, tree, parent_id, indent):
    """
    Recursive helper function to write tree nodes to the report file.
    """
    for child_id in tree.get_children(parent_id):
        text = tree.item(child_id, "text")
        values = tree.item(child_id, "values")
        if values:
            status = values[0]
            file_handle.write(f"{indent}{text} - [{status}]\n")
            _write_tree_node_to_file(file_handle, tree, child_id, indent + "  ")

def show_error_log(parent, errors):
    """
    Creates and displays a Toplevel window showing a list of errors.
    """
    win = tk.Toplevel(parent)
    win.title("Processing Errors")
    win.geometry("600x400")
    
    text_frame = ttk.Frame(win)
    text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    text = tk.Text(text_frame, height=15, width=80, wrap="word")
    scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    for err in errors:
        text.insert(tk.END, f"- {err}\n\n")
    text.config(state="disabled")
    
    ttk.Button(win, text="Export Log...", command=lambda: export_errors_to_file(errors)).pack(pady=5)

def export_errors_to_file(errors):
    """
    Saves the list of processing errors to a text file.
    """
    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt")],
        title="Export Error Log"
    )
    if file_path:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("FileConsolidator Error Log\n" + "="*30 + "\n\n")
                f.write("\n".join(errors))
            messagebox.showinfo("Export Successful", f"Error log saved to {file_path}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Failed to save error log: {e}")

def show_completion_message(parent, total_files, error_count, output_filename):
    """
    Displays a success message after processing, offering to open the file.
    """
    success_msg = f"Success! Consolidated {total_files - error_count} of {total_files} files."
    if error_count > 0:
        success_msg += f"\n\nEncountered {error_count} errors. Check the error log for details."
    
    if messagebox.askyesno("Operation Complete", f"{success_msg}\n\nDo you want to open the file?"):
        try:
            os.startfile(output_filename)
        except AttributeError:
            # For non-Windows OS
            import subprocess
            try:
                subprocess.call(['open', output_filename]) # macOS
            except:
                try:
                    subprocess.call(['xdg-open', output_filename]) # Linux
                except:
                     messagebox.showerror("Error", f"Could not open file automatically. Please find it at:\n{output_filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")
