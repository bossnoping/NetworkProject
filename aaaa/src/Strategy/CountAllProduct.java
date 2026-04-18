import java.util.List;

public class CountAllProduct  implements CounterStrategy<Product> {
    @Override
    public int count(List<Product> data) {
        int count = 0;
        for (Product product : data) {
            count += 1;
        }
        return count;
    }
}
