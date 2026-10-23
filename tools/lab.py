#!/usr/bin/env python3
"""Small Tk interface for running isolated Phonendo instances."""
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab_docker import DockerSession, DockerInstance, PORTS

KINDS = ('reader', 'manager', 'verifier', 'storage')


class Lab:
    def __init__(self, root):
        self.root, self.instances, self.events = root, {}, queue.Queue()
        self.session = DockerSession(self.events)
        self.busy = False
        self.closing = False
        self.destroyed = False
        self.polling = False
        root.title('Phonendo · Laboratorio Docker')
        root.geometry('1220x920')
        root.minsize(1050, 780)
        style = ttk.Style(root)
        style.theme_use('clam')
        root.configure(background='#f4f7fb')
        style.configure('.', background='#f4f7fb', font=('sans', 10))
        style.configure('TNotebook.Tab', padding=(18, 10))
        style.configure('Treeview', rowheight=30, font=('sans', 11))
        style.configure('Treeview.Heading', font=('sans', 11, 'bold'), padding=8)
        style.configure('TButton', padding=(10, 6))
        ttk.Label(root, text='Phonendo · Docker', font=('sans', 20, 'bold'), padding=10).pack(anchor='w')
        ttk.Label(root, text='Puerto local → puerto del contenedor. Las conexiones entre servicios usan la URL Docker.', padding=(12, 0)).pack(anchor='w')
        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(fill='x')
        self.kind = tk.StringVar(value='reader')
        kinds = ttk.Combobox(toolbar, textvariable=self.kind, values=KINDS, state='readonly', width=12)
        kinds.pack(side='left')
        kinds.bind('<<ComboboxSelected>>', lambda _: self.defaults())
        self.name, self.port = tk.StringVar(value='reader-1'), tk.StringVar(value='7101')
        for label, variable in [('Nombre', self.name), ('Puerto local', self.port)]:
            ttk.Label(toolbar, text=label).pack(side='left', padx=5)
            ttk.Entry(toolbar, textvariable=variable, width=15).pack(side='left')
        ttk.Button(toolbar, text='Crear contenedor', command=lambda: self.safe(self.start)).pack(side='left', padx=8)
        controls = ttk.Frame(root, padding=(8, 4))
        controls.pack(fill='x')
        for label, action in [('Parar', 'stop'), ('Reanudar / Arrancar', 'resume'), ('Pausar', 'pause')]:
            ttk.Button(controls, text=label, command=lambda action=action: self.safe(lambda: self.control(action))).pack(side='left', padx=3)
        ttk.Button(controls, text='Abrir en navegador', command=lambda: self.safe(self.open_url)).pack(side='left', padx=3)
        self.status = tk.StringVar(value='Preparado · necesita Docker en ejecución')
        ttk.Label(controls, textvariable=self.status).pack(side='right', padx=8)
        self.table = ttk.Treeview(root, columns=('service','port','internal','url','state'), show='tree headings', height=5)
        self.table.heading('#0', text='Instancia')
        for key, label in [('service','Servicio'),('port','Puerto local'),('internal','Puerto contenedor'),('url','URL Docker'),('state','Estado')]:
            self.table.heading(key, text=label)
        self.table.column('#0', width=150)
        for column in ('service','port','internal','state'):
            self.table.column(column, width=140, anchor='center')
        self.table.column('url', width=260)
        self.table.tag_configure('running', foreground='#176c43')
        self.table.tag_configure('paused', foreground='#a56a00')
        self.table.tag_configure('exited', foreground='#a33030')
        self.table.pack(fill='x', padx=8)
        self.table.bind('<<TreeviewSelect>>', self.select)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True, padx=8, pady=8)
        config_tab = ttk.Frame(self.tabs, padding=10)
        reader_tab = ttk.Frame(self.tabs, padding=10)
        logs_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(config_tab, text='Configuración')
        self.tabs.add(reader_tab, text='Dispositivos y sensores')
        self.tabs.add(logs_tab, text='Logs')
        ttk.Label(config_tab, text='Configuración JSON: editable antes de arrancar; selecciona una instancia para consultar su configuración.').pack(anchor='w', padx=8)
        self.config = ScrolledText(config_tab, height=10, font=('monospace', 10), undo=True)
        self.config.pack(fill='both', expand=True, padx=8)
        ttk.Button(config_tab, text='Nueva configuración', command=self.defaults).pack(anchor='w', padx=8)
        form = ttk.LabelFrame(reader_tab, text='Reader seleccionado · dispositivos, sensores y observaciones', padding=8)
        self.reader_form = form
        form.pack(fill='x', padx=8, pady=5)
        self.fields = {}
        fields = [('device','Dispositivo','device-1'),('sensor','Sensor','temperature-1'),
                  ('property','Propiedad','temperature'),('unit','Unidad','CELSIUS'),
                  ('value','Valor JSON','23.5'),('values','Serie JSON','[20, 21, 22, 23]'),('interval','Intervalo (s)','1')]
        for index, (key,label,default) in enumerate(fields):
            row, col = divmod(index, 4)
            ttk.Label(form, text=label).grid(row=row*2, column=col, sticky='w', padx=4)
            variable = tk.StringVar(value=default)
            self.fields[key] = variable
            ttk.Entry(form, textvariable=variable, width=24).grid(row=row*2+1, column=col, sticky='ew', padx=4)
        actions = ttk.Frame(form)
        actions.grid(row=4, column=0, columnspan=4, pady=8)
        for label, action in [('Añadir dispositivo/sensor','add'),('Ver dispositivos','list'),('Enviar valor','emit'),
                              ('Iniciar serie','periodic'),('Parar serie','stop'),('Eliminar sensor','remove_sensor'),('Eliminar dispositivo','remove_device')]:
            ttk.Button(actions, text=label, command=lambda action=action: self.safe(lambda: self.send(action))).pack(side='left', padx=2)
        self.device_table = ttk.Treeview(reader_tab, columns=('sensors',), height=6)
        self.device_table.heading('#0', text='Dispositivo')
        self.device_table.heading('sensors', text='Sensores')
        self.device_table.pack(fill='both', expand=True, pady=12)
        ttk.Label(logs_tab, text='Logs y respuestas de las instancias').pack(anchor='w', padx=8)
        self.logs = ScrolledText(logs_tab, height=12, state='disabled', background='#152331', foreground='#dfeaf4', insertbackground='white', font=('monospace', 10))
        self.logs.pack(fill='both', expand=True, padx=8, pady=5)
        self.defaults()
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.refresh)
        root.after(1000, self.poll_states)

    def safe(self, action):
        try:
            action()
        except Exception as error:
            messagebox.showerror('Phonendo', str(error))

    def defaults(self):
        kind = self.kind.get()
        number = 1
        while kind + '-' + str(number) in self.instances:
            number += 1
        self.name.set(kind + '-' + str(number))
        used = {i.port for i in self.instances.values()}
        port = 7101 + KINDS.index(kind)
        while port in used:
            port += 4
        self.port.set(str(port))
        config = json.loads((ROOT / 'apps' / kind / 'config.json').read_text())
        def endpoint(service):
            target = next((i for i in self.instances.values() if i.kind == service), None)
            return target.docker_url if target else f'http://{service}-1:{PORTS[service]}'
        if kind == 'manager':
            config.setdefault('subscriptions', {}).update(readers=[], verifiers=[], storages=[])
            config['services'].update(verifiers=[endpoint('verifier')], storages=[endpoint('storage')])
        elif kind == 'reader':
            config['services']['managers'] = [{'url': endpoint('manager'), 'token': self.session.credentials['API_TOKEN_MANAGER']}]
            config['readerId'] = self.name.get()
        else:
            config.setdefault('subscriptions', {})['managers'] = []
        config.setdefault('server', {}).update(host='0.0.0.0', port=PORTS[kind])
        self.config.delete('1.0','end')
        self.config.insert('1.0',json.dumps(config, indent=2))

    def task(self, description, action, done=None):
        if self.busy:
            raise ValueError('Espera a que termine la operación actual')
        self.busy = True
        self.status.set(description)
        def work():
            error = None
            value = None
            try:
                value = action()
            except Exception as caught:
                error = str(caught)
            def finish():
                self.busy = False
                self.status.set('Preparado' if error is None else 'Error · consulta el mensaje')
                if error:
                    self.closing = False
                    messagebox.showerror('Docker', error)
                elif done:
                    done(value)
            self.events.put(('__call__', finish))
        threading.Thread(target=work, daemon=True).start()

    def selected(self):
        selection = self.table.selection()
        if not selection:
            raise ValueError('Selecciona una instancia de la tabla')
        return self.instances[selection[0]]

    def select(self, _event=None):
        if not self.table.selection():
            return
        instance = self.selected()
        self.reader_form.configure(text=('Reader: ' + instance.name if instance.kind == 'reader' else 'Selecciona un Reader para gestionar dispositivos'))
        self.device_table.delete(*self.device_table.get_children())
        self.config.delete('1.0','end')
        self.config.insert('1.0', json.dumps(instance.config, indent=2))

    def start(self):
        name = self.name.get().strip()
        if not name or name in self.instances:
            raise ValueError('Usa un nombre nuevo para cada instancia')
        kind, port = self.kind.get(), int(self.port.get())
        config = json.loads(self.config.get('1.0','end'))
        def created(instance):
            self.instances[name] = instance
            self.table.insert('', 'end', iid=name, text=name,
                values=(kind, port, instance.internal_port, instance.docker_url, 'Arrancando'))
            self.table.selection_set(name)
        self.task('Construyendo y arrancando ' + name + '…',
                  lambda: DockerInstance(self.session, kind, name, port, config), created)

    def control(self, action):
        instance = self.selected()
        self.task(action + ': ' + instance.name + '…', getattr(instance, action))

    def open_url(self):
        instance = self.selected()
        path = '/health' if instance.kind == 'reader' else '/raw' if instance.kind == 'storage' else '/'
        webbrowser.open(instance.url + path)

    def send(self, action):
        body = {key: variable.get() for key,variable in self.fields.items()}
        body['action'] = action
        if action == 'emit':
            body['value'] = json.loads(body['value'])
        if action == 'periodic':
            body['values'] = json.loads(body['values'])
            body['interval'] = float(body['interval'])
        instance = self.selected()
        self.task('Enviando al Reader…', lambda: instance.command(body), self.show_devices)

    def show_devices(self, result):
        self.device_table.delete(*self.device_table.get_children())
        for device in result.get('devices', []):
            self.device_table.insert('', 'end', text=device['device'], values=(', '.join(device['sensors']),))

    def refresh(self):
        while not self.events.empty():
            name, line = self.events.get_nowait()
            if name == '__call__':
                line()
                if self.destroyed:
                    return
                continue
            self.logs.configure(state='normal')
            self.logs.insert('end',f'[{name}] {line}')
            # Bound the UI log so periodic generators do not grow memory forever.
            if int(self.logs.index('end-1c').split('.')[0]) > 2000:
                self.logs.delete('1.0','200.0')
            self.logs.see('end')
            self.logs.configure(state='disabled')
        self.root.after(150,self.refresh)

    def poll_states(self):
        if not self.polling and not self.closing:
            self.polling = True
            instances = list(self.instances.items())
            def check():
                states = []
                for name, instance in instances:
                    try:
                        states.append((name, instance.state()))
                    except Exception:
                        states.append((name, 'unavailable'))
                def apply():
                    labels = {'running':'En ejecución', 'paused':'Pausado', 'exited':'Parado',
                              'created':'Creado', 'unavailable':'No disponible', 'restarting':'Reiniciando'}
                    for name, state in states:
                        if self.table.exists(name):
                            self.table.set(name, 'state', labels.get(state, state))
                            self.table.item(name, tags=(state,))
                    self.polling = False
                self.events.put(('__call__', apply))
            threading.Thread(target=check, daemon=True).start()
        if not self.closing:
            self.root.after(2000,self.poll_states)

    def close(self):
        if self.busy:
            messagebox.showinfo('Phonendo', 'Espera a que termine la operación antes de cerrar.')
            return
        self.closing = True
        def finished(_value):
            self.destroyed = True
            self.root.destroy()
        self.task('Eliminando contenedores del laboratorio…', self.session.close, finished)


if __name__ == '__main__':
    root = tk.Tk()
    application = Lab(root)
    try:
        root.mainloop()
    finally:
        if application.session.connected:
            application.session.close()
