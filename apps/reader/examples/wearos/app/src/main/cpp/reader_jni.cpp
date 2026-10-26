// Capa JNI fina sobre WearReader. Existe solo para cruzar la frontera con
// Kotlin; la lógica está en wear_reader.cpp, que se prueba sin JNI.
//
// Invariantes:
// - Una sola instancia por proceso, creada en init() y nunca reemplazada: los
//   hilos SSE guardan ids de suscriptor que serían inválidos en otra.
// - Toda llamada a la librería pasa por gMutex: ReaderCore, ReaderService y
//   ObservationStream no son seguros entre hilos, y aquí llaman a la vez Health
//   Services, cada conexión HTTP y cada cliente SSE.
// - Las cadenas cruzan como byte[] en UTF-8: NewStringUTF usa UTF-8 modificado
//   y estropearía los caracteres fuera del plano básico.
#include <jni.h>

#include <memory>
#include <mutex>
#include <string>

#include "wear_reader.h"

namespace {

std::mutex gMutex;
std::unique_ptr<WearReader> gReader;

std::string toString(JNIEnv* env, jbyteArray bytes) {
    if (bytes == nullptr) return std::string();
    const jsize length = env->GetArrayLength(bytes);
    std::string out(static_cast<std::size_t>(length), '\0');
    if (length > 0) env->GetByteArrayRegion(bytes, 0, length, reinterpret_cast<jbyte*>(&out[0]));
    return out;
}

jbyteArray toBytes(JNIEnv* env, const std::string& value) {
    jbyteArray bytes = env->NewByteArray(static_cast<jsize>(value.size()));
    if (bytes != nullptr && !value.empty()) {
        env->SetByteArrayRegion(bytes, 0, static_cast<jsize>(value.size()),
                                reinterpret_cast<const jbyte*>(value.data()));
    }
    return bytes;
}

// Prefijo de pollFrame: 'E' evento, 'C' stream cerrado. Empty devuelve null.
constexpr char kFrameEvent = 'E';
constexpr char kFrameClosed = 'C';

}  // namespace

#define JNI_FN(name) Java_org_phonendo_reader_wearos_NativeReader_##name

extern "C" {

JNIEXPORT jboolean JNICALL JNI_FN(nativeInit)(JNIEnv* env, jobject, jbyteArray readerId, jint queueSize) {
    std::lock_guard<std::mutex> lock(gMutex);
    if (!gReader) {
        gReader.reset(new WearReader(toString(env, readerId),
                                     static_cast<std::size_t>(queueSize > 0 ? queueSize : 64)));
    }
    return gReader->lastError().empty() ? JNI_TRUE : JNI_FALSE;
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeIngest)(JNIEnv* env, jobject, jdouble bpm, jlong epochMillis) {
    std::lock_guard<std::mutex> lock(gMutex);
    if (!gReader) return nullptr;
    std::string envelope;
    if (!gReader->ingestHeartRate(bpm, static_cast<std::int64_t>(epochMillis), envelope)) return nullptr;
    return toBytes(env, envelope);
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeLastError)(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    return toBytes(env, gReader ? gReader->lastError() : std::string("reader not initialized"));
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeMetadata)(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    return gReader ? toBytes(env, gReader->metadataJson()) : nullptr;
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeDevices)(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    return gReader ? toBytes(env, gReader->devicesJson()) : nullptr;
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeDevice)(JNIEnv* env, jobject, jbyteArray deviceId) {
    const std::string id = toString(env, deviceId);
    std::lock_guard<std::mutex> lock(gMutex);
    std::string body;
    if (!gReader || !gReader->deviceJson(id, body)) return nullptr;
    return toBytes(env, body);
}

JNIEXPORT jint JNICALL JNI_FN(nativeSubscribe)(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    return gReader ? static_cast<jint>(gReader->subscribe()) : 0;
}

JNIEXPORT void JNICALL JNI_FN(nativeUnsubscribe)(JNIEnv*, jobject, jint id) {
    std::lock_guard<std::mutex> lock(gMutex);
    if (gReader) gReader->unsubscribe(static_cast<SubscriberId>(id));
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativePollFrame)(JNIEnv* env, jobject, jint id) {
    std::lock_guard<std::mutex> lock(gMutex);
    std::string frame;
    const StreamPoll result = gReader ? gReader->pollFrame(static_cast<SubscriberId>(id), frame)
                                      : StreamPoll::Unknown;
    if (result == StreamPoll::Empty) return nullptr;
    if (result == StreamPoll::Event) return toBytes(env, std::string(1, kFrameEvent) + frame);
    if (frame.empty()) frame = sseStreamClosed();
    return toBytes(env, std::string(1, kFrameClosed) + frame);
}

JNIEXPORT jint JNICALL JNI_FN(nativeSubscriberCount)(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    return gReader ? static_cast<jint>(gReader->subscriberCount()) : 0;
}

JNIEXPORT void JNICALL JNI_FN(nativeClose)(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(gMutex);
    if (gReader) gReader->close();
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeSseConnected)(JNIEnv* env, jobject) {
    return toBytes(env, sseConnected());
}

JNIEXPORT jbyteArray JNICALL JNI_FN(nativeSseHeartbeat)(JNIEnv* env, jobject) {
    return toBytes(env, sseHeartbeat());
}

}  // extern "C"
