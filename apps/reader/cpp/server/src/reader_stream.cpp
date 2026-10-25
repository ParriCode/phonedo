#include "reader_stream.h"
#include "reader_serialization.h"

ObservationStream::ObservationStream(std::size_t queueSize)
    : queueSize(queueSize), nextId(1) {
    if (queueSize < 1) lastError = "stream queueSize must be a positive integer";
}

bool ObservationStream::isValid() const {
    return queueSize >= 1;
}

const std::string& ObservationStream::getLastError() const {
    return lastError;
}

SubscriberId ObservationStream::subscribe() {
    if (!isValid()) return 0;
    if (nextId == 0) nextId = 1;
    Subscriber subscriber{nextId++, false, {}};
    subscribers.push_back(subscriber);
    return subscriber.id;
}

void ObservationStream::unsubscribe(SubscriberId id) {
    for (auto it = subscribers.begin(); it != subscribers.end(); ++it) {
        if (it->id == id) {
            subscribers.erase(it);
            return;
        }
    }
}

void ObservationStream::disconnect(Subscriber& subscriber) {
    subscriber.closed = true;
    subscriber.queue.clear();
}

void ObservationStream::publish(const std::string& eventJson) {
    for (auto& subscriber : subscribers) {
        if (subscriber.closed) continue;
        if (subscriber.queue.size() >= queueSize) {
            disconnect(subscriber);
        } else {
            subscriber.queue.push_back(eventJson);
        }
    }
}

StreamPoll ObservationStream::poll(SubscriberId id, std::string& out) {
    Subscriber* subscriber = find(id);
    if (subscriber == nullptr) return StreamPoll::Unknown;
    if (subscriber->closed) {
        unsubscribe(id);
        return StreamPoll::Closed;
    }
    if (subscriber->queue.empty()) return StreamPoll::Empty;
    out = subscriber->queue.front();
    subscriber->queue.pop_front();
    return StreamPoll::Event;
}

std::size_t ObservationStream::pending(SubscriberId id) const {
    const Subscriber* subscriber = find(id);
    return subscriber == nullptr ? 0 : subscriber->queue.size();
}

std::size_t ObservationStream::subscriberCount() const {
    std::size_t count = 0;
    for (const auto& subscriber : subscribers) {
        if (!subscriber.closed) count++;
    }
    return count;
}

void ObservationStream::close() {
    for (auto& subscriber : subscribers) disconnect(subscriber);
}

ObservationStream::Subscriber* ObservationStream::find(SubscriberId id) {
    for (auto& subscriber : subscribers) {
        if (subscriber.id == id) return &subscriber;
    }
    return nullptr;
}

const ObservationStream::Subscriber* ObservationStream::find(SubscriberId id) const {
    for (const auto& subscriber : subscribers) {
        if (subscriber.id == id) return &subscriber;
    }
    return nullptr;
}

bool StreamOutput::publish(const std::string& readerId, const Observation& observation) {
    stream.publish(observationEventToJson(readerId, observation));
    return true;
}

std::string sseConnected() {
    return ": connected\n\n";
}

std::string sseHeartbeat() {
    return ": heartbeat\n\n";
}

std::string sseObservation(const std::string& eventJson) {
    return "event: observation\ndata: " + eventJson + "\n\n";
}

std::string sseStreamClosed() {
    return "event: stream_closed\ndata: {}\n\n";
}
