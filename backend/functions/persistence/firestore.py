"""Optional production Firestore transaction adapter.
Install firebase-admin/google-cloud-firestore in the deployment environment.
"""
class FirestoreTransactionStore:
    def __init__(self, client=None):
        if client is None:
            try:
                from firebase_admin import firestore
                client=firestore.client()
            except Exception as exc:
                raise RuntimeError('Firebase Admin SDK is required for FirestoreStore') from exc
        self.client=client
    def run_transaction(self, fn):
        transaction=self.client.transaction()
        return transaction.call(lambda tx: fn(tx))
    def get(self, collection, doc_id):
        snap=self.client.collection(collection).document(doc_id).get()
        return snap.to_dict() if snap.exists else None
    def create(self, collection, doc_id, value):
        self.client.collection(collection).document(doc_id).create(value)
    def update(self, collection, doc_id, value):
        self.client.collection(collection).document(doc_id).set(value, merge=True)
