#include "../src/core.h"
#include "../src/serializer.h"

#include <memory>
#include <string>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using namespace pybind11::literals;

static std::string objectToString(const py::object& value) {
    if (value.is_none()) {
        return "";
    }
    if (py::hasattr(value, "isoformat")) {
        return py::str(value.attr("isoformat")());
    }
    return py::str(value);
}

static py::object emptyAsNone(const std::string& value) {
    if (value.empty()) {
        return py::none();
    }
    return py::str(value);
}

class BoundReaderCore {
public:
    BoundReaderCore(const std::string& readerId, bool allowNewDevices, bool allowNewSensors)
        : core(readerId, ReaderPolicy{allowNewDevices, allowNewSensors}) {
    }

    bool addDevice(const Device& device) {
        auto ownedDevice = std::make_unique<Device>(device.deviceId, device.deviceType, device.platform);
        for (std::uint8_t i = 0; i < device.sensorCount(); i++) {
            Sensor* sensor = const_cast<Device&>(device).sensorAt(i);
            if (sensor == nullptr) {
                continue;
            }
            auto ownedSensor = std::make_unique<Sensor>(
                sensor->observableProperty,
                sensor->procedure,
                sensor->featureOfInterest,
                sensor->sensorId,
                sensor->unit,
                ownedDevice->deviceId
            );
            if (!ownedDevice->addSensor(*ownedSensor)) {
                core.lastError = "could not add sensor: " + sensor->sensorId;
                return false;
            }
            sensors.push_back(std::move(ownedSensor));
        }
        if (!core.addDevice(*ownedDevice)) {
            return false;
        }
        devices.push_back(std::move(ownedDevice));
        return true;
    }

    bool addSensor(
        const std::string& deviceId,
        const Sensor& sensor
    ) {
        Device* device = core.getDevice(deviceId);
        if (device == nullptr) {
            return false;
        }
        auto ownedSensor = std::make_unique<Sensor>(
            sensor.observableProperty,
            sensor.procedure,
            sensor.featureOfInterest,
            sensor.sensorId,
            sensor.unit,
            deviceId
        );
        if (!device->addSensor(*ownedSensor)) {
            core.lastError = "could not add sensor: " + sensor.sensorId;
            return false;
        }
        sensors.push_back(std::move(ownedSensor));
        return true;
    }

    py::object handleMeasurementData(const Observation& measurement) {
        Observation output;
        if (!core.handleMeasurementData(measurement, &output)) {
            return py::none();
        }
        return py::cast(output);
    }

    ReaderCore core;
    std::vector<std::unique_ptr<Device>> devices;
    std::vector<std::unique_ptr<Sensor>> sensors;
};

PYBIND11_MODULE(_phonendo_reader_core, m) {
    py::class_<Observation>(m, "Observation")
        .def(
            py::init([](
                const std::string& observableProperty,
                py::object simpleResult,
                py::object phenomenonTime,
                const std::string& featureOfInterest,
                const std::string& procedure,
                py::object deviceId,
                py::object sensorId,
                py::object unit,
                py::object observationId
            ) {
                return Observation(
                    observableProperty,
                    objectToString(simpleResult),
                    objectToString(phenomenonTime),
                    featureOfInterest,
                    procedure,
                    objectToString(deviceId),
                    objectToString(sensorId),
                    objectToString(unit),
                    objectToString(observationId)
                );
            }),
            py::arg("observable_property") = "",
            py::arg("simple_result") = "",
            py::arg("phenomenon_time") = "",
            py::arg("feature_of_interest") = "",
            py::arg("procedure") = "",
            py::arg("device_id") = py::none(),
            py::arg("sensor_id") = py::none(),
            py::arg("unit") = py::none(),
            py::arg("observation_id") = ""
        )
        .def_property("observable_property", [](const Observation& self) { return self.observableProperty; }, [](Observation& self, const std::string& value) { self.observableProperty = value; })
        .def_property("simple_result", [](const Observation& self) { return self.simpleResult; }, [](Observation& self, py::object value) { self.simpleResult = objectToString(value); })
        .def_property("phenomenon_time", [](const Observation& self) { return self.phenomenonTime; }, [](Observation& self, py::object value) { self.phenomenonTime = objectToString(value); })
        .def_property("feature_of_interest", [](const Observation& self) { return self.featureOfInterest; }, [](Observation& self, const std::string& value) { self.featureOfInterest = value; })
        .def_property("procedure", [](const Observation& self) { return self.procedure; }, [](Observation& self, const std::string& value) { self.procedure = value; })
        .def_property("device_id", [](const Observation& self) { return emptyAsNone(self.deviceId); }, [](Observation& self, py::object value) { self.deviceId = objectToString(value); })
        .def_property("sensor_id", [](const Observation& self) { return emptyAsNone(self.sensorId); }, [](Observation& self, py::object value) { self.sensorId = objectToString(value); })
        .def_property("unit", [](const Observation& self) { return emptyAsNone(self.unit); }, [](Observation& self, py::object value) { self.unit = objectToString(value); })
        .def_property("observation_id", [](const Observation& self) { return self.observationId; }, [](Observation& self, const std::string& value) { self.observationId = value; })
        .def("to_dict", [](const Observation& self) {
            return py::dict(
                "observation_id"_a = self.observationId,
                "observable_property"_a = self.observableProperty,
                "simple_result"_a = self.simpleResult,
                "phenomenon_time"_a = self.phenomenonTime,
                "feature_of_interest"_a = self.featureOfInterest,
                "procedure"_a = self.procedure,
                "unit"_a = emptyAsNone(self.unit)
            );
        });

    py::class_<Sensor>(m, "Sensor")
        .def(
            py::init([](
                const std::string& observableProperty,
                const std::string& procedure,
                const std::string& featureOfInterest,
                py::object sensorId,
                py::object unit,
                py::object deviceId
            ) {
                return Sensor(
                    observableProperty,
                    procedure,
                    featureOfInterest,
                    objectToString(sensorId),
                    objectToString(unit),
                    objectToString(deviceId)
                );
            }),
            py::arg("observable_property"),
            py::arg("procedure"),
            py::arg("feature_of_interest"),
            py::arg("sensor_id") = "",
            py::arg("unit") = py::none(),
            py::arg("device_id") = py::none()
        )
        .def_static("fromJson", [](py::dict data, py::object defaultDeviceId) {
            auto get = [&](const char* key, const char* fallback) {
                return data.contains(key) ? objectToString(data[key]) : std::string(fallback);
            };
            return Sensor(
                get("observable_property", "unknown"),
                get("procedure", "configured-measurement"),
                get("feature_of_interest", "unknown-feature"),
                get("sensor_id", "unknown"),
                data.contains("unit") ? objectToString(data["unit"]) : "",
                data.contains("device_id") ? objectToString(data["device_id"]) : objectToString(defaultDeviceId)
            );
        }, py::arg("json_data"), py::arg("default_device_id") = py::none())
        .def_property("sensor_id", [](const Sensor& self) { return self.sensorId; }, [](Sensor& self, const std::string& value) { self.sensorId = value; })
        .def_property("observable_property", [](const Sensor& self) { return self.observableProperty; }, [](Sensor& self, const std::string& value) { self.observableProperty = value; })
        .def_property("procedure", [](const Sensor& self) { return self.procedure; }, [](Sensor& self, const std::string& value) { self.procedure = value; })
        .def_property("feature_of_interest", [](const Sensor& self) { return self.featureOfInterest; }, [](Sensor& self, const std::string& value) { self.featureOfInterest = value; })
        .def_property("unit", [](const Sensor& self) { return emptyAsNone(self.unit); }, [](Sensor& self, py::object value) { self.unit = objectToString(value); })
        .def_property("device_id", [](const Sensor& self) { return emptyAsNone(self.deviceId); }, [](Sensor& self, py::object value) { self.deviceId = objectToString(value); });

    py::class_<Device>(m, "Device", py::dynamic_attr())
        .def(
            py::init([](const std::string& deviceId, const std::string& deviceType, const std::string&, py::object platform) {
                if (deviceId.empty()) {
                    throw py::value_error("device_id no puede estar vacío");
                }
                return Device(deviceId, deviceType, objectToString(platform));
            }),
            py::arg("device_id"),
            py::arg("device_type") = "device",
            py::arg("_legacy_address") = "",
            py::arg("platform") = py::none()
        )
        .def_static("fromJson", [](py::dict data, py::object defaultDeviceId) {
            std::string deviceId = data.contains("device_id") ? objectToString(data["device_id"]) : objectToString(defaultDeviceId);
            std::string deviceType = "device";
            if (data.contains("device_type")) {
                deviceType = objectToString(data["device_type"]);
            } else if (data.contains("deviceType")) {
                deviceType = objectToString(data["deviceType"]);
            }
            Device device(deviceId, deviceType, data.contains("platform") ? objectToString(data["platform"]) : "");
            if (data.contains("comm")) {
                py::cast(device).attr("comm") = data["comm"];
            } else if (data.contains("com")) {
                py::cast(device).attr("comm") = data["com"];
            }
            return device;
        }, py::arg("json_data"), py::arg("default_device_id") = py::none())
        .def_property("device_id", [](const Device& self) { return self.deviceId; }, [](Device& self, const std::string& value) { self.deviceId = value; })
        .def_property("device_type", [](const Device& self) { return self.deviceType; }, [](Device& self, const std::string& value) { self.deviceType = value; })
        .def_property("platform", [](const Device& self) { return emptyAsNone(self.platform); }, [](Device& self, py::object value) { self.platform = objectToString(value); })
        .def("add_sensor", [](Device& self, Sensor& sensor) {
            if (!self.addSensor(sensor)) {
                throw py::value_error("Ya existe un sensor con id '" + sensor.sensorId + "' en el dispositivo '" + self.deviceId + "'");
            }
        }, py::keep_alive<1, 2>())
        .def("has_sensor", &Device::hasSensor)
        .def("get_sensor", &Device::getSensor, py::return_value_policy::reference_internal);

    py::class_<BoundReaderCore>(m, "_NativeReaderCore")
        .def(py::init<const std::string&, bool, bool>(), py::arg("reader_id") = "", py::arg("allow_new_devices") = true, py::arg("allow_new_sensors") = true)
        .def_property_readonly("reader_id", [](const BoundReaderCore& self) { return self.core.readerId; })
        .def_property_readonly("last_error", [](const BoundReaderCore& self) { return self.core.lastError; })
        .def("add_device", &BoundReaderCore::addDevice)
        .def("add_sensor", &BoundReaderCore::addSensor)
        .def("has_device", [](const BoundReaderCore& self, const std::string& deviceId) { return self.core.hasDevice(deviceId); })
        .def("device_has_sensor", [](BoundReaderCore& self, const std::string& deviceId, const std::string& sensorId) {
            Device* device = self.core.getDevice(deviceId);
            return device != nullptr && device->hasSensor(sensorId);
        })
        .def("device_count", [](const BoundReaderCore& self) { return self.core.deviceCount(); })
        .def("handle_measurement_data", &BoundReaderCore::handleMeasurementData);

    m.def("serialize_sosa_ttl", &serializeSosaTTL, py::arg("observation"));
}
