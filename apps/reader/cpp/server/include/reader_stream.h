#ifndef PHONENDO_READER_STREAM_H
#define PHONENDO_READER_STREAM_H

#include "reader_service.h"
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

// Reparto en vivo como stream.py: cada suscriptor tiene su cola acotada de
// eventos JSON. Sin hilos: el adaptador de plataforma vacía las colas con
// poll() desde su bucle. No es seguro llamarlo desde varios hilos a la vez.

#ifndef PHONENDO_SSE_HEARTBEAT_MS
#define PHONENDO_SSE_HEARTBEAT_MS 15000
#endif

using SubscriberId = std::uint32_t;  // 0 nunca es un suscriptor válido

enum class StreamPoll {
    Empty,    // nada pendiente
    Event,    // out contiene un evento
    Closed,   // desconectado (cola llena o close()); se olvida tras avisar
    Unknown   // id inexistente o ya retirado
};

class ObservationStream {
public:
    explicit ObservationStream(std::size_t queueSize = 256);

    bool isValid() const;
    const std::string& getLastError() const;

    SubscriberId subscribe();
    void unsubscribe(SubscriberId id);
    // Un suscriptor con la cola llena se desconecta en vez de bloquear al resto.
    void publish(const std::string& eventJson);
    StreamPoll poll(SubscriberId id, std::string& out);
    std::size_t pending(SubscriberId id) const;
    // Suscriptores activos (sin contar los desconectados pendientes de aviso).
    std::size_t subscriberCount() const;
    void close();

private:
    struct Subscriber {
        SubscriberId id;
        bool closed;
        std::deque<std::string> queue;
    };

    Subscriber* find(SubscriberId id);
    const Subscriber* find(SubscriberId id) const;
    static void disconnect(Subscriber& subscriber);

    std::size_t queueSize;
    SubscriberId nextId;
    std::vector<Subscriber> subscribers;
    std::string lastError;
};

// Puerto de salida que publica el sobre del evento en el stream.
class StreamOutput : public ObservationOutput {
public:
    explicit StreamOutput(ObservationStream& stream) : stream(stream) {}
    bool publish(const std::string& readerId, const Observation& observation) override;

private:
    ObservationStream& stream;
};

// Tramas SSE idénticas a las de server.py.
std::string sseConnected();
std::string sseHeartbeat();
std::string sseObservation(const std::string& eventJson);
std::string sseStreamClosed();

#endif
