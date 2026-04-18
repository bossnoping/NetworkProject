import javax.smartcardio.Card;

public class CardMeasurable implements Measurable {
    private CreditCard card;
    public CardMeasurable(CreditCard card) {
        this.card = card;
    }
    @Override
    public double getMeasure() {
        return card.getBalance();
    }
}
