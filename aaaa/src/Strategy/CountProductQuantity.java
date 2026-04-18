import java.util.List;

public class CountProductQuantity implements CounterStrategy<Product> {

    @Override
    public int count(List<Product> data) {
        int total = 0;
        for (Product p : data) {
            total += p.getQuantity();
        }
        return total;
    }
}
