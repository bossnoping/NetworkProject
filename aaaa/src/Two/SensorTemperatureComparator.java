package Two;

import One.Sensor;

public class SensorTemperatureComparator implements Comparator<Sensor> {
    @Override
    public int compare(Sensor o1, Sensor o2) {
        return Double.compare(o1.getTemperature(), o2.getTemperature());
    }
}
