public class CreditCard {
    private double balance; // ยอดใช้จ่าย
    private String name;
    public CreditCard(String name, double balance) {
        this.name = name;
        this.balance = balance;
    }
    public double getBalance() {
        return balance;
    }
}