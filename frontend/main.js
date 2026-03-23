const productsList = document.getElementById("products");
const loadProductsBtn = document.getElementById("load-products");
const orderForm = document.getElementById("order-form");
const orderResult = document.getElementById("order-result");

loadProductsBtn.addEventListener("click", async () => {
  productsList.innerHTML = "";
  const response = await fetch("/api/catalog/products");
  const products = await response.json();

  products.forEach((product) => {
    const li = document.createElement("li");
    li.textContent = `${product.name} - ${product.price} EUR`;
    productsList.appendChild(li);
  });
});

orderForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    customerName: document.getElementById("customer").value,
    items: [
      {
        productName: document.getElementById("product").value,
        quantity: Number(document.getElementById("qty").value),
        unitPrice: Number(document.getElementById("price").value)
      }
    ]
  };

  const response = await fetch("/api/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  const body = await response.json();
  orderResult.textContent = JSON.stringify(body, null, 2);
});
