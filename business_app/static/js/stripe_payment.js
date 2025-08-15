document.addEventListener('DOMContentLoaded', async () => {
    // Check if the Stripe publishable key is available
    if (typeof STRIPE_PUBLISHABLE_KEY === 'undefined' || !STRIPE_PUBLISHABLE_KEY) {
        console.error('Stripe publishable key is not set. Please set STRIPE_PUBLISHABLE_KEY in your environment.');
        showMessage('Error: Payment gateway is not configured correctly. Please contact support.');
        return;
    }

    const stripe = Stripe(STRIPE_PUBLISHABLE_KEY);

    let elements;

    const paymentForm = document.querySelector('#payment-form');
    // If the payment form doesn't exist on this page, do nothing.
    if (!paymentForm) {
        return;
    }

    // --- 1. Create a Payment Intent on the server ---
    // In a real application, the amount and currency would be dynamic.
    // For this example, we'll use a fixed amount.
    const { clientSecret, error: backendError } = await fetch('/create-payment-intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            amount: 2000, // Example: $20.00 USD, passed in cents
            currency: 'usd',
        }),
    }).then(r => r.json());

    if (backendError) {
        showMessage(`Could not initialize payment: ${backendError.message}`);
        return;
    }

    // --- 2. Initialize Stripe Elements with the Payment Intent's client secret ---
    elements = stripe.elements({ clientSecret });
    const paymentElement = elements.create('payment');
    paymentElement.mount('#payment-element');


    // --- 3. Handle Form Submission ---
    paymentForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        setLoading(true);

        const { error } = await stripe.confirmPayment({
            elements,
            confirmParams: {
                // Redirect to the same page after payment. The webhook will handle the rest.
                return_url: `${window.location.origin}/`,
            },
        });

        // This point is only reached if there's an immediate error confirming the payment.
        // Otherwise, the user is redirected to the `return_url`.
        if (error.type === "card_error" || error.type === "validation_error") {
            showMessage(error.message);
        } else {
            showMessage("An unexpected error occurred.");
        }

        setLoading(false);
    });

    // --- UI Helper Functions ---
    function showMessage(messageText) {
        const messageContainer = document.querySelector("#payment-message");
        messageContainer.style.display = "block";
        messageContainer.textContent = messageText;
        setTimeout(() => {
            messageContainer.style.display = "none";
            messageContainer.textContent = "";
        }, 5000); // Hide message after 5 seconds
    }

    function setLoading(isLoading) {
        const submitButton = document.querySelector("#submit-button");
        const spinner = document.querySelector("#spinner");
        const buttonText = document.querySelector("#button-text");

        if (isLoading) {
            submitButton.disabled = true;
            spinner.style.display = "inline-block";
            buttonText.style.display = "none";
        } else {
            submitButton.disabled = false;
            spinner.style.display = "none";
            buttonText.style.display = "inline-block";
        }
    }
});
