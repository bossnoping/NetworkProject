package Strategy2;

public class SwitchStrategy implements EmailStrategy {
    @Override
    public void send(EmailSystem emailSystem, Email email) {
        emailSystem.sendSwitchCipher(email); // เรียกเมธอดเดิม
    }
}
