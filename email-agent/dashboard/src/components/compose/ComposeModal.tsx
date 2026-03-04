"use client";

import Modal from "@/components/ui/Modal";
import ComposeForm from "./ComposeForm";

interface ComposeModalProps {
  open: boolean;
  onClose: () => void;
  replyTo?: { messageId: string; to: string; subject: string };
}

export default function ComposeModal({ open, onClose, replyTo }: ComposeModalProps) {
  return (
    <Modal open={open} onClose={onClose} title={replyTo ? "Reply" : "New Email"}>
      <ComposeForm replyTo={replyTo} onSuccess={onClose} />
    </Modal>
  );
}
