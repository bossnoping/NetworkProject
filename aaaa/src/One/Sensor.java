public class Sensor {
    private int sensorID;
    private double temperature; // อุณหภูมิ
    public Sensor(int sensorID, double temperature) {
        this.sensorID = sensorID;
        this.temperature = temperature;
    }
    public double getTemperature() {
        return temperature;
    }

}