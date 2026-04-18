package Strategy2;

public class CaesarStrategy implements EmailStrategy {
    private int key;

    public CaesarStrategy(int key) {
        this.key = key;
    }

    @Override
    public void send(EmailSystem emailSystem, Email email) {
        emailSystem.sendCaesar(email, key); // เรียกเมธอดเดิม
    }
}
