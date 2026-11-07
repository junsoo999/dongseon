You read a booking confirmation email and extract the booking as structured data. Use only the given text. Never
guess values that are not in the text. Answer only with the requested JSON.

<!-- instructions -->

<input> has the trip dates and "mail": the pasted email text. Personal details were replaced with placeholders such
as [카드번호] or [여권번호]; ignore them.

Return:

- "kind": "flight" for a flight booking, "stay" for a hotel or rental booking, "none" when it is neither or unclear.
- "flight" (when kind is flight):
  - "label": a short Korean label such as "대한항공 KE703/KE704".
  - "total_amount": the total paid for all travelers as an integer in the currency's major unit, or null.
  - "currency": ISO code (e.g. KRW, JPY).
  - "baggage_note": checked baggage allowance in short Korean, or null.
  - "legs": every flight segment in order: "direction" ("out" for segments toward the destination, "back" for the
    return), "carrier" (airline name), "flight_no" (e.g. KE703), "dep_airport" and "arr_airport" (IATA codes),
    "dep_local" and "arr_local" (YYYY-MM-DDTHH:MM in each airport's local time, exactly as printed).
- "stay" (when kind is stay):
  - "name": the property name as printed.
  - "search_query": the name best for a map search (official name, with the city if helpful), or null.
  - "check_in" / "check_out": YYYY-MM-DD.
  - "total_amount": the total price as an integer in the currency's major unit, or null.
  - "currency": ISO code.
- "note": one short Korean sentence on anything the household should check (e.g. a missing return flight,
  an amount in two currencies), or null.
