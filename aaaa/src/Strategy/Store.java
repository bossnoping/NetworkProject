import java.util.ArrayList;
import java.util.List;

public class Store {
    private List<Product> products;
    public Store() { products = new ArrayList<>(); }
    public void addProduct(String name, double price, int quantity) {
        products.add(new Product(name, price, quantity));
    }
    public List<Product> getProducts() {
        return products;
    }
}