import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import requests
import json

class RouterControl:
    def __init__(self, router_ip, username, password):
        self.router_ip = router_ip
        self.username = username
        self.password = password
        self.session_id = None

    def get_session_id(self):
        url = f"http://{self.router_ip}/cgi-bin/lua.cgi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Accept": "text/plain, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Priority": "u=0"
        }
        data = {
            "cmd": 100,
            "method": "POST",
            "username": self.username,
            "passwd": self.password
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    self.session_id = result.get("sessionId")
                    return self.session_id
        except requests.RequestException:
            pass
        return None

    def change_lte_bands(self, bands):
        if not self.session_id:
            if not self.get_session_id():
                return False

        url = f"http://{self.router_ip}/cgi-bin/lua.cgi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Accept": "text/plain, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Priority": "u=0"
        }
        data = {
            "band": bands,
            "method": "POST",
            "cmd": 166,
            "sessionId": self.session_id
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result.get("success", False)
        except requests.RequestException:
            pass
        return False

    def get_current_bands(self):
        if not self.session_id:
            if not self.get_session_id():
                return None

        url = f"http://{self.router_ip}/cgi-bin/lua.cgi"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
            "Accept": "text/plain, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Priority": "u=0"
        }
        data = {
            "cmd": 165,
            "method": "GET",
            "sessionId": self.session_id
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("lockband", [])
        except requests.RequestException:
            pass
        return None

class LTEBandControlGUI(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=(20, 10))
        self.pack(fill=BOTH, expand=YES)
        
        self.router = None
        self.available_bands = ["EUTRAN_BAND1", "EUTRAN_BAND3", "EUTRAN_BAND5", "EUTRAN_BAND38", "EUTRAN_BAND41"]
        self.credentials_visible = False
        self.create_widgets()
        self.auto_connect()

    def create_widgets(self):
        # Credentials Frame (initially hidden)
        self.credentials_frame = ttk.Frame(self)
        self.credentials_frame.grid(row=0, column=0, columnspan=2, sticky=(W, E), pady=5)
        self.credentials_frame.grid_remove()

        # Router IP
        ttk.Label(self.credentials_frame, text="Router IP:").grid(row=0, column=0, sticky=W, pady=5)
        self.ip_entry = ttk.Entry(self.credentials_frame)
        self.ip_entry.insert(0, "192.168.1.1")
        self.ip_entry.grid(row=0, column=1, sticky=(W, E), pady=5)

        # Username
        ttk.Label(self.credentials_frame, text="Username:").grid(row=1, column=0, sticky=W, pady=5)
        self.username_entry = ttk.Entry(self.credentials_frame)
        self.username_entry.insert(0, "administrator")
        self.username_entry.grid(row=1, column=1, sticky=(W, E), pady=5)

        # Password
        ttk.Label(self.credentials_frame, text="Password:").grid(row=2, column=0, sticky=W, pady=5)
        self.password_entry = ttk.Entry(self.credentials_frame, show="*")
        self.password_entry.insert(0, "f6b489579bb7f5ceb4d3d94d0874a68c")
        self.password_entry.grid(row=2, column=1, sticky=(W, E), pady=5)

        # Toggle Credentials Button
        self.toggle_credentials_button = ttk.Button(self, text="⚙", width=3, command=self.toggle_credentials)
        self.toggle_credentials_button.grid(row=0, column=0, sticky=W, pady=5)

        # Connect Button (initially hidden)
        self.connect_button = ttk.Button(self, text="Connect", command=self.connect_router, style="Accent.TButton")
        self.connect_button.grid(row=1, column=0, columnspan=2, pady=10)
        self.connect_button.grid_remove()

        # Band Selection
        self.band_label = ttk.Label(self, text="Select LTE Bands:")
        self.band_label.grid(row=2, column=0, columnspan=2, pady=(10, 5))

        self.band_vars = []
        for i, band in enumerate(self.available_bands):
            var = ttk.BooleanVar()
            self.band_vars.append(var)
            cb = ttk.Checkbutton(self, text=f"Band {band.split('_')[-1]}", variable=var, state="disabled")
            cb.grid(row=3+i, column=0, columnspan=2, sticky=W)

        # Change Band Button
        self.change_button = ttk.Button(self, text="Change Bands", command=self.change_bands, state="disabled")
        self.change_button.grid(row=8, column=0, columnspan=2, pady=10)

        # Current Bands Label
        self.current_bands_label = ttk.Label(self, text="Current Bands: None", wraplength=250)
        self.current_bands_label.grid(row=9, column=0, columnspan=2, pady=5)

        # Status Label
        self.status_label = ttk.Label(self, text="", wraplength=250)
        self.status_label.grid(row=10, column=0, columnspan=2, pady=5)

    def toggle_credentials(self):
        if self.credentials_visible:
            self.credentials_frame.grid_remove()
            self.connect_button.grid_remove()
        else:
            self.credentials_frame.grid()
            self.connect_button.grid()
        self.credentials_visible = not self.credentials_visible

    def auto_connect(self):
        self.connect_router()

    def connect_router(self):
        ip = self.ip_entry.get()
        username = self.username_entry.get()
        password = self.password_entry.get()

        self.router = RouterControl(ip, username, password)
        if self.router.get_session_id():
            self.status_label.config(text="Successfully connected to router", bootstyle="success")
            for cb in self.winfo_children():
                if isinstance(cb, ttk.Checkbutton):
                    cb.config(state="normal")
            self.change_button.config(state="normal")
            self.update_current_bands()
        else:
            self.status_label.config(text="Failed to connect to router", bootstyle="danger")

    def change_bands(self):
        selected_bands = [band for band, var in zip(self.available_bands, self.band_vars) if var.get()]
        if selected_bands:
            if self.router.change_lte_bands(selected_bands):
                self.status_label.config(text=f"Successfully changed bands", bootstyle="success")
                self.update_current_bands()
            else:
                self.status_label.config(text="Failed to change bands", bootstyle="danger")
        else:
            self.status_label.config(text="Please select at least one band", bootstyle="warning")

    def update_current_bands(self):
        current_bands = self.router.get_current_bands()
        if current_bands is not None:
            band_numbers = [band.split('_')[-1] for band in current_bands]
            self.current_bands_label.config(text=f"Current Bands: {', '.join(band_numbers)}")
            for var, band in zip(self.band_vars, self.available_bands):
                var.set(band in current_bands)
        else:
            self.current_bands_label.config(text="Failed to fetch current bands")

def main():
    root = ttk.Window("LTE Band Control", "darkly")
    LTEBandControlGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()