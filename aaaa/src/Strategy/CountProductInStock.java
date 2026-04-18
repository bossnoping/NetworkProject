import java.util.List;

public class CountProductInStock implements CounterStrategy<Product> {
    @Override
    public int count(List<Product> data) {
        int count = 0;
        for (Product product : data) {
            if (product.getQuantity() > 0)
                count += 1;
        }
        return count;
    }
}
