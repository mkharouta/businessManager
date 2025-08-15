document.addEventListener('DOMContentLoaded', () => {
    const coinbaseForm = document.querySelector('#coinbase-payment-form');
    if (!coinbaseForm) {
        return; // Do nothing if the form is not on the page
    }

    const coinbaseButton = document.querySelector('#coinbase-submit-button');
    const statusContainer = document.querySelector('#coinbase-status');

    coinbaseForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Show loading state
        if (coinbaseButton) coinbaseButton.disabled = true;
        if (statusContainer) {
            statusContainer.textContent = 'Connecting to Coinbase...';
            statusContainer.style.display = 'block';
        }

        try {
            const response = await fetch('/create-coinbase-charge', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                // In a real app, this amount would be dynamic (e.g., from an input field or data attribute)
                body: JSON.stringify({
                    amount: 2000, // Example: $20.00 USD, passed in cents
                    currency: 'usd',
                }),
            });

            const data = await response.json();

            if (!response.ok || data.error) {
                const errorMessage = data.error ? data.error.message : 'An unknown error occurred.';
                throw new Error(errorMessage);
            }

            if (data.hosted_url) {
                // Redirect the user to the Coinbase payment page
                window.location.href = data.hosted_url;
            } else {
                throw new Error('Could not retrieve payment URL from Coinbase.');
            }

        } catch (error) {
            console.error('Coinbase charge creation failed:', error);
            if (statusContainer) statusContainer.textContent = `Error: ${error.message}`;
            if (coinbaseButton) coinbaseButton.disabled = false;
        }
    });
});
