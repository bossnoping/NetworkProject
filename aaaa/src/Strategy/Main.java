
import java.util.Collections;
import java.util.List;

public class Main {
    public static void main(String[] args) {
        Store store = new Store();
        store.addProduct("Big Java", 300, 5);
        store.addProduct("Da Vinci Code", 120, 0);
        store.addProduct("Python 101", 200, 10);

        CounterStrategy<Product> counterAll = new CountAllProduct();
        CounterStrategy<Product> counterInStock = new CountProductInStock();
        CounterStrategy<Product> counterQuantity = new CountProductQuantity();

        List<Product> products = store.getProducts();

        int allProduct = counterAll.count(products);
        int inStock = counterInStock.count(products);
        int totalQuantity = counterQuantity.count(products);

        System.out.println("จำนวนสินค้าทั้งหมด: " + allProduct);
        System.out.println("จำนวนสินค้าที่มีในสต็อก: " + inStock);
        System.out.println("จำนวนรวมของสินค้า (ชิ้น): " + totalQuantity);
    }
}
