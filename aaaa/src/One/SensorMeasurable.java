public class SensorMeasurable implements Measurable {
    private Sensor sensor;
    public SensorMeasurable(Sensor sensor) {
        this.sensor = sensor;
    }

    @Override
    public double getMeasure() {
        return sensor.getTemperature();
    }
}
