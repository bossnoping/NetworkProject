import java.util.List;

public interface CounterStrategy<T> {
    int count(List<T> data);

}
