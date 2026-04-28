import time


def send_task_created_email(
    recipient_email: str,
    username: str,
    task_title: str,
    task_id: int,
) -> None:
    """
    Simula l'invio di una email di notifica alla creazione di un task.

    In produzione qui chiameresti smtplib, SendGrid, SES, ecc.
    Viene eseguita in background — il client ha già ricevuto la risposta 201.
    """
    # Simula latenza di rete/SMTP
    time.sleep(1)

    print("\n" + "━" * 42)
    print("📧  EMAIL DI NOTIFICA [background]")
    print("━" * 42)
    print(f"A:        {recipient_email}")
    print("Oggetto:  Nuovo task creato!")
    print("Corpo:")
    print(f"  Ciao {username},")
    print(f"  Il tuo task #{task_id} '{task_title}' è stato creato.")
    print("  Buon lavoro!")
    print("━" * 42 + "\n")
