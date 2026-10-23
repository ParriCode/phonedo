import hmac
import json
import queue
from flask import Response, abort, request

def stream_response(stream, token):
    supplied = request.headers.get('Authorization', '')
    if not token or not hmac.compare_digest(supplied, 'Bearer ' + token):
        abort(401)

    def events():
        with stream.subscribe() as subscriber:
            yield ': connected\n\n'
            while True:
                try:
                    event = subscriber.get(timeout=15)
                except queue.Empty:
                    yield ': heartbeat\n\n'
                    continue
                if event is None:
                    yield 'event: stream_closed\ndata: {}\n\n'
                    break
                yield ('event: observation\nid: ' + str(event['key']) + '\ndata: '
                       + json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n\n')

    return Response(events(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

