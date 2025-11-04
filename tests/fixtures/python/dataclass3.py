# --- Version A: The Original ---
def calculate_total_price(items, tax_rate):
    """Calculates the final price including tax."""
    subtotal = 0
    for item in items:
        subtotal += item.price

    final_price = subtotal * (1 + tax_rate)
    return final_price


# --- Version B: Renamed and Reformatted ---
def get_final_cost(products, vat):
    # Computes the total cost with VAT.
    cost = 0
    for p in products:
        cost += p.price  # Compacted line

    total = cost * (1 + vat)
    return total
