"""GUI operations with a real Docker Reader; requires an X display."""
import json
import os
from pathlib import Path
import socket
import sys
import time

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Necesita una sesión gráfica o Xvfb')
def test_ui_pause_stop_and_resume(monkeypatch):
    import tkinter as tk
    from lab import Lab
    root = tk.Tk()
    app = Lab(root)
    errors = []
    monkeypatch.setattr('lab.messagebox.showerror', lambda title, text: errors.append(text))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    app.port.set(str(port))
    app.name.set('reader-ui')
    app.config.delete('1.0', 'end')
    app.config.insert('1.0', json.dumps({'readerId':'reader-ui', 'server':{'enabled':True},
                                       'services':{'managers':[]}}))
    def wait(check, seconds=60):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            root.update()
            assert not errors, errors
            try:
                if check():
                    return
            except requests.RequestException:
                pass
            time.sleep(.05)
        raise AssertionError('Operación de interfaz no completada')
    try:
        app.start()
        wait(lambda: not app.busy and bool(app.instances))
        wait(lambda: requests.get(f'http://127.0.0.1:{port}/health',timeout=.5).status_code==200)
        app.tabs.select(1)
        app.send('add')
        wait(lambda: not app.busy)
        assert len(app.device_table.get_children()) == 1
        for action, state in [('pause','paused'), ('resume','running'), ('stop','exited'), ('resume','running')]:
            app.control(action)
            wait(lambda: not app.busy)
            assert app.selected().state() == state
        wait(lambda: requests.get(f'http://127.0.0.1:{port}/health',timeout=.5).status_code==200)
        app.send('list')
        wait(lambda: not app.busy)
        assert len(app.device_table.get_children()) == 1
    finally:
        app.session.close()
        root.destroy()
