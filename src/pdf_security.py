"""
PDF Security module.
Provides encryption, decryption, password protection, and permissions management.
Uses pikepdf for robust encryption support.
"""

import pikepdf
from pathlib import Path
from src.utils import logger, safe_operation, validate_pdf_path, generate_output_filename


class PDFSecurity:
    """Handles PDF security operations using pikepdf."""

    # ─── Encryption ──────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def encrypt_pdf(pdf_path, user_password, owner_password=None,
                    output_path=None, permissions=None):
        """
        Encrypt a PDF with password protection.

        Args:
            pdf_path: Path to the PDF file
            user_password: Password required to open the PDF
            owner_password: Password for full access (defaults to user_password)
            output_path: Output file path
            permissions: Dict of permissions, keys:
                - print: Allow printing (default True)
                - modify: Allow modification (default False)
                - copy: Allow copying text (default False)
                - annotate: Allow annotations (default False)
                - fill_forms: Allow form filling (default True)

        Returns:
            Path to the encrypted PDF
        """
        pdf_path = validate_pdf_path(pdf_path)
        if owner_password is None:
            owner_password = user_password

        # Default permissions
        if permissions is None:
            permissions = {
                "print": True,
                "modify": False,
                "copy": False,
                "annotate": False,
                "fill_forms": True,
            }

        # Build pikepdf permissions
        allow = pikepdf.Permissions(
            print_lowres=permissions.get("print", True),
            print_highres=permissions.get("print", True),
            modify_other=permissions.get("modify", False),
            modify_annotation=permissions.get("annotate", False),
            modify_form=permissions.get("fill_forms", True),
            modify_assembly=permissions.get("modify", False),
            extract=permissions.get("copy", False),
            accessibility=True,
        )

        pdf = pikepdf.open(str(pdf_path))

        if output_path is None:
            output_path = generate_output_filename(pdf_path, "encrypted")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf.save(
            str(output_path),
            encryption=pikepdf.Encryption(
                owner=owner_password,
                user=user_password,
                allow=allow,
                aes=True,
                R=6  # AES-256
            )
        )
        pdf.close()

        logger.info(f"Encrypted PDF saved to: {output_path}")
        return output_path

    # ─── Decryption ──────────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def decrypt_pdf(pdf_path, password, output_path=None):
        """
        Decrypt a password-protected PDF.

        Args:
            pdf_path: Path to the encrypted PDF
            password: Password to unlock the PDF
            output_path: Output file path

        Returns:
            Path to the decrypted PDF
        """
        pdf_path = validate_pdf_path(pdf_path)

        try:
            pdf = pikepdf.open(str(pdf_path), password=password)
        except pikepdf.PasswordError:
            raise ValueError("Incorrect password")

        if output_path is None:
            output_path = generate_output_filename(pdf_path, "decrypted")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save without encryption
        pdf.save(str(output_path))
        pdf.close()

        logger.info(f"Decrypted PDF saved to: {output_path}")
        return output_path

    # ─── Remove Password ─────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def remove_password(pdf_path, password, output_path=None):
        """
        Remove password protection from a PDF.

        Args:
            pdf_path: Path to the encrypted PDF
            password: Current password
            output_path: Output file path

        Returns:
            Path to the unprotected PDF
        """
        return PDFSecurity.decrypt_pdf(pdf_path, password, output_path)

    # ─── Check Encryption ────────────────────────────────────────────────

    @staticmethod
    def is_encrypted(pdf_path):
        """
        Check if a PDF is encrypted.

        Args:
            pdf_path: Path to the PDF

        Returns:
            True if the PDF is encrypted
        """
        pdf_path = validate_pdf_path(pdf_path)
        try:
            pdf = pikepdf.open(str(pdf_path))
            encrypted = pdf.is_encrypted
            pdf.close()
            return encrypted
        except pikepdf.PasswordError:
            return True

    @staticmethod
    def get_security_info(pdf_path, password=None):
        """
        Get security information about a PDF.

        Args:
            pdf_path: Path to the PDF
            password: Password if encrypted

        Returns:
            Dictionary with security info
        """
        pdf_path = validate_pdf_path(pdf_path)

        info = {
            "is_encrypted": False,
            "needs_password": False,
            "permissions": {},
            "encryption_method": None,
        }

        try:
            pdf = pikepdf.open(str(pdf_path), password=password or "")
            info["is_encrypted"] = pdf.is_encrypted

            if pdf.is_encrypted:
                # Try to get permissions
                try:
                    allow = pdf.allow
                    info["permissions"] = {
                        "print_lowres": allow.print_lowres,
                        "print_highres": allow.print_highres,
                        "modify_other": allow.modify_other,
                        "modify_annotation": allow.modify_annotation,
                        "modify_form": allow.modify_form,
                        "extract": allow.extract,
                        "accessibility": allow.accessibility,
                    }
                except Exception:
                    pass

            pdf.close()

        except pikepdf.PasswordError:
            info["is_encrypted"] = True
            info["needs_password"] = True

        return info

    # ─── Change Password ─────────────────────────────────────────────────

    @staticmethod
    @safe_operation
    def change_password(pdf_path, old_password, new_user_password,
                        new_owner_password=None, output_path=None):
        """
        Change the password of an encrypted PDF.

        Args:
            pdf_path: Path to the encrypted PDF
            old_password: Current password
            new_user_password: New user password
            new_owner_password: New owner password (defaults to user password)
            output_path: Output file path

        Returns:
            Path to the re-encrypted PDF
        """
        pdf_path = validate_pdf_path(pdf_path)

        if new_owner_password is None:
            new_owner_password = new_user_password

        try:
            pdf = pikepdf.open(str(pdf_path), password=old_password)
        except pikepdf.PasswordError:
            raise ValueError("Incorrect current password")

        if output_path is None:
            output_path = generate_output_filename(pdf_path, "newpass")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf.save(
            str(output_path),
            encryption=pikepdf.Encryption(
                owner=new_owner_password,
                user=new_user_password,
                aes=True,
                R=6
            )
        )
        pdf.close()

        logger.info(f"Password changed, saved to: {output_path}")
        return output_path
