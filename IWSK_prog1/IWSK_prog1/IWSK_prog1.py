import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import time
from datetime import datetime

class UARTApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UART Communicator")
        self.root.geometry("800x650")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.serial_port = None
        self.history = []  # Przechowuje krotki: (timestamp, kierunek, tekst)
        
        self.ping_start_time = 0
        self.is_waiting_for_pong = False

        self.setup_ui()
        self.refresh_ports()
        
        # Pętla odczytu non-blocking
        self.root.after(100, self.read_from_port)

    def setup_ui(self):
        # --- RAMKA KONFIGURACJI ---
        config_frame = ttk.LabelFrame(self.root, text="1. Konfiguracja lacza")
        config_frame.pack(fill="x", padx=10, pady=5)

        # Port
        ttk.Label(config_frame, text="Port COM:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.cb_ports = ttk.Combobox(config_frame, width=15, state="readonly")
        self.cb_ports.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="Odswiez", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=5)

        # Baudrate
        ttk.Label(config_frame, text="Baudrate:").grid(row=0, column=3, padx=5, pady=5, sticky="e")
        self.cb_baud = ttk.Combobox(config_frame, values=[150, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 38400, 57600, 115200], width=10, state="readonly")
        self.cb_baud.set(9600)
        self.cb_baud.grid(row=0, column=4, padx=5, pady=5)

        # Format znaku (Bity danych, Parzystość, Bity stopu)
        ttk.Label(config_frame, text="Bity danych:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.cb_bytesize = ttk.Combobox(config_frame, values=["7", "8"], width=5, state="readonly")
        self.cb_bytesize.set("8")
        self.cb_bytesize.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Parzystosc:").grid(row=1, column=2, padx=5, pady=5, sticky="e")
        self.cb_parity = ttk.Combobox(config_frame, values=["None (N)", "Even (E)", "Odd (O)"], width=10, state="readonly")
        self.cb_parity.set("None (N)")
        self.cb_parity.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Bity stopu:").grid(row=1, column=4, padx=5, pady=5, sticky="e")
        self.cb_stopbits = ttk.Combobox(config_frame, values=["1", "2"], width=5, state="readonly")
        self.cb_stopbits.set("1")
        self.cb_stopbits.grid(row=1, column=5, padx=5, pady=5, sticky="w")

        # Kontrola przepływu
        ttk.Label(config_frame, text="Kontrola przeplywu:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.cb_flow = ttk.Combobox(config_frame, values=["Brak", "Sprzetowa (RTS/CTS)", "Sprzetowa (DTR/DSR)", "Programowa (XON/XOFF)"], width=20, state="readonly")
        self.cb_flow.set("Brak")
        self.cb_flow.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        # Terminator
        ttk.Label(config_frame, text="Terminator:").grid(row=2, column=3, padx=5, pady=5, sticky="e")
        self.cb_terminator = ttk.Combobox(config_frame, values=["Brak", "CR (\\r)", "LF (\\n)", "CR-LF (\\r\\n)"], width=15, state="readonly")
        self.cb_terminator.set("CR-LF (\\r\\n)")
        self.cb_terminator.grid(row=2, column=4, columnspan=2, padx=5, pady=5, sticky="w")

        # Przyciski połączenia
        self.btn_connect = ttk.Button(config_frame, text="Polacz", command=self.connect_serial)
        self.btn_connect.grid(row=3, column=0, columnspan=2, pady=10)
        self.btn_disconnect = ttk.Button(config_frame, text="Rozlacz", command=self.disconnect_serial, state="disabled")
        self.btn_disconnect.grid(row=3, column=2, columnspan=2, pady=10)

        # --- RAMKA PING ---
        ping_frame = ttk.LabelFrame(self.root, text="5. PING (Round Trip Delay)")
        ping_frame.pack(fill="x", padx=10, pady=5)
        self.btn_ping = ttk.Button(ping_frame, text="Wyslij PING", command=self.send_ping, state="disabled")
        self.btn_ping.pack(side="left", padx=5, pady=5)
        self.lbl_ping_result = ttk.Label(ping_frame, text="Czas odpowiedzi: --- ms")
        self.lbl_ping_result.pack(side="left", padx=15, pady=5)

        # --- RAMKA KOMUNIKACJI (Nadawanie / Odbiór) ---
        comm_frame = ttk.Frame(self.root)
        comm_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Nadawanie
        tx_frame = ttk.LabelFrame(comm_frame, text="2/6.1 Nadawanie (Tekstowy)")
        tx_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.txt_tx = tk.Text(tx_frame, height=15, width=40)
        self.txt_tx.pack(fill="both", expand=True, padx=5, pady=5)
        self.btn_send = ttk.Button(tx_frame, text="Wyslij", command=self.send_data, state="disabled")
        self.btn_send.pack(pady=5)

        # Odbiór
        rx_frame = ttk.LabelFrame(comm_frame, text="3/6.1 Odbior")
        rx_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        self.txt_rx = tk.Text(rx_frame, height=15, width=40, state="disabled")
        self.txt_rx.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Button(rx_frame, text="Wyczysc", command=self.clear_rx).pack(pady=5)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [port.device for port in ports]
        self.cb_ports['values'] = port_list
        if port_list:
            self.cb_ports.set(port_list[0])
        else:
            self.cb_ports.set("Brak portow")

    def connect_serial(self):
        port = self.cb_ports.get()
        if port == "Brak portow" or not port:
            messagebox.showerror("Blad", "Nie wybrano poprawnego portu COM!")
            return

        try:
            # Parsowanie ustawień
            baud = int(self.cb_baud.get())
            bytesize = serial.EIGHTBITS if self.cb_bytesize.get() == "8" else serial.SEVENBITS
            
            parity_str = self.cb_parity.get()
            if "N" in parity_str: parity = serial.PARITY_NONE
            elif "E" in parity_str: parity = serial.PARITY_EVEN
            else: parity = serial.PARITY_ODD

            stopbits = serial.STOPBITS_ONE if self.cb_stopbits.get() == "1" else serial.STOPBITS_TWO

            flow_str = self.cb_flow.get()
            xonxoff = True if "XON" in flow_str else False
            rtscts = True if "RTS" in flow_str else False
            dsrdtr = True if "DTR" in flow_str else False

            self.serial_port = serial.Serial(
                port=port,
                baudrate=baud,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                xonxoff=xonxoff,
                rtscts=rtscts,
                dsrdtr=dsrdtr,
                timeout=0 # Non-blocking do pętli zdarzeń UI
            )

            self.btn_connect.config(state="disabled")
            self.btn_disconnect.config(state="normal")
            self.btn_send.config(state="normal")
            self.btn_ping.config(state="normal")
            self.log_history("SYSTEM", f"Polaczono z {port} przy {baud} baud.")
            messagebox.showinfo("Sukces", f"Otwarto port {port}")

        except Exception as e:
            messagebox.showerror("Blad polaczenia", str(e))

    def disconnect_serial(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.log_history("SYSTEM", "Rozlaczono.")
            
        self.btn_connect.config(state="normal")
        self.btn_disconnect.config(state="disabled")
        self.btn_send.config(state="disabled")
        self.btn_ping.config(state="disabled")

    def get_terminator_bytes(self):
        term = self.cb_terminator.get()
        if term == "CR (\\r)": return b'\r'
        elif term == "LF (\\n)": return b'\n'
        elif term == "CR-LF (\\r\\n)": return b'\r\n'
        return b''

    def send_data(self):
        if self.serial_port and self.serial_port.is_open:
            data_str = self.txt_tx.get("1.0", tk.END).strip("\n") # Pobierz tekst bez dodatkowego entera tkintera
            if data_str:
                data_bytes = data_str.encode('utf-8') + self.get_terminator_bytes()
                try:
                    self.serial_port.write(data_bytes)
                    self.log_history("TX", data_str)
                    self.txt_tx.delete("1.0", tk.END) # Wyczyść bufor po wysłaniu
                except Exception as e:
                    messagebox.showerror("Blad transmisji", str(e))

    def send_ping(self):
        if self.serial_port and self.serial_port.is_open:
            self.ping_start_time = time.time()
            self.is_waiting_for_pong = True
            self.lbl_ping_result.config(text="Oczekiwanie...")
            # Wysyłamy specjalną sekwencję. Drugi program musi na nią odpowiedzieć.
            self.serial_port.write(b'__PING__\r\n')
            self.log_history("SYSTEM", "Wyslano zadanie PING")

    def read_from_port(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                data = self.serial_port.read(1024)
                if data:
                    text_data = data.decode('utf-8', errors='replace')
                    
                    # Automatyczna odpowiedź na PING (dla testowania z drugim komputerem)
                    if '__PING__' in text_data:
                        self.serial_port.write(b'__PONG__\r\n')
                        text_data = text_data.replace('__PING__', '[Odebrano PING, wyslano odpowiedz]')
                    
                    # Odbiór PONG i obliczenie opóźnienia
                    if '__PONG__' in text_data and self.is_waiting_for_pong:
                        rtt = (time.time() - self.ping_start_time) * 1000
                        self.lbl_ping_result.config(text=f"Czas odpowiedzi: {rtt:.2f} ms")
                        self.is_waiting_for_pong = False
                        text_data = text_data.replace('__PONG__', '[Odebrano odpowiedz PONG]')

                    self.txt_rx.config(state="normal")
                    self.txt_rx.insert(tk.END, text_data)
                    self.txt_rx.see(tk.END)
                    self.txt_rx.config(state="disabled")
                    self.log_history("RX", text_data.strip())
            except Exception as e:
                print("Blad odczytu:", e)

        # Zapętlaj funkcję co 100ms
        self.root.after(100, self.read_from_port)

    def log_history(self, direction, text):
        if text:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.history.append(f"[{timestamp}] {direction}: {text}")

    def clear_rx(self):
        self.txt_rx.config(state="normal")
        self.txt_rx.delete("1.0", tk.END)
        self.txt_rx.config(state="disabled")

    def on_closing(self):
        if self.history:
            if messagebox.askyesno("Wyjscie", "Czy chcesz zapisac historie konwersacji do pliku?"):
                filepath = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt")],
                    title="Zapisz"
                )
                if filepath:
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write("\n".join(self.history))
                        messagebox.showinfo("Sukces", "Historia zostala zapisana.")
                    except Exception as e:
                        messagebox.showerror("Blad zapisu", str(e))
        
        self.disconnect_serial()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = UARTApp(root)
    root.mainloop()